# ⚠️ 개인정보 안내
# 이 스크립트는 게임 로그에서 인증 토큰을 읽어
# 공식 서버(ef-webview.gryphline.com)에만 전송합니다.
# 토큰은 외부 서버로 전송되지 않으며, 로컬에 저장되지 않습니다.
import os
import re
import csv
import time
from urllib.parse import urlparse, parse_qs

# 필수 외부 라이브러리 설치 확인
try:
    import requests
    from scipy.stats import binom
except ImportError as e:
    missing = str(e).split("'")[1]
    print(f"❌ 필수 라이브러리 '{missing}'가 설치되어 있지 않습니다.")
    print("👉 아래 명령어로 한 번에 설치해주세요:")
    print("   pip install -r requirements.txt")
    exit()

def extract_gacha_url_from_log():
    print("🔍 게임 로그에서 가챠 기록 주소를 찾는 중...")
    log_path = os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Gryphline\Endfield\sdklogs\HGWebview.log")
    url_pattern = re.compile(r"https://[^\s]+u8_token=[^\s]+")
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines):
                match = url_pattern.search(line)
                if match and "/page/giftcode" not in match.group(0):
                    return match.group(0)
    except FileNotFoundError:
        print("❌ 로그 파일을 찾을 수 없습니다. 게임 내에서 '가챠 기록' 창을 먼저 한 번 열어주세요!")
        return None
    return None

def fetch_and_save_all_records(url, csv_filename="endfield_gacha_history_all.csv"):
    if not url: return False
    
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    token = query_params.get('u8_token', query_params.get('token', [None]))[0]
    
    if not token:
        print("❌ 토큰을 찾을 수 없습니다. 게임 내 가챠 기록 창을 다시 열어주세요.")
        return False
        
    print("✅ 인증 토큰 추출 성공! 서버에서 데이터를 불러옵니다. (기록이 많을수록 1~2분 정도 소요됩니다)")

    gacha_pools = [
        {"name": "기초 헤드헌팅", "api": "https://ef-webview.gryphline.com/api/record/char", "pool_type": "E_CharacterGachaPoolType_Standard"},
        {"name": "특별 허가 헤드헌팅", "api": "https://ef-webview.gryphline.com/api/record/char", "pool_type": "E_CharacterGachaPoolType_Special"},
        {"name": "여정의 시작 헤드헌팅", "api": "https://ef-webview.gryphline.com/api/record/char", "pool_type": "E_CharacterGachaPoolType_Beginner"},
        {"name": "무기 가챠", "api": "https://ef-webview.gryphline.com/api/record/weapon", "pool_type": "E_WeaponGachaPoolType_Standard"} 
    ]

    all_records = []

    for pool in gacha_pools:
        print(f"▶️ [{pool['name']}] 수집 중 ", end="", flush=True)
        has_more = True
        seq_id = ""
        pool_count = 0
        
        while has_more:
            params = {"server_id": 2, "pool_type": pool["pool_type"], "lang": "ko-kr", "token": token}
            if seq_id: params["seq_id"] = seq_id

            try:
                response = requests.get(pool["api"], params=params)
                response.raise_for_status()
                data = response.json()
                
                code = data.get('code')
                if code != 0:
                    if code == 401:
                        print("❌ 토큰이 만료되었습니다. 게임에서 기록 창을 다시 열어주세요.")
                    else:
                        print(f"❌ 서버 응답 오류 (code: {code})")
                    break
                    
                records = data.get('data', {}).get('list', [])
                if not records: break
                    
                all_records.extend(records)
                pool_count += len(records)
                
                print(".", end="", flush=True)
                
                has_more = data.get('data', {}).get('hasMore', False)
                if has_more:
                    seq_id = records[-1]['seqId']
                    time.sleep(1.0) 
            except requests.exceptions.RequestException as e:
                print(f"❌ 네트워크 오류: {e}")
                break
            except Exception as e:
                print(f"❌ 예상치 못한 오류: {e}")
                break

        
        print(f" 완료! ({pool_count}개)")
        time.sleep(2.0)

    if all_records:
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            all_keys = []
            for record in all_records:
                for key in record.keys():
                    if key not in all_keys: all_keys.append(key)
            
            writer = csv.DictWriter(csvfile, fieldnames=all_keys)
            writer.writeheader()
            for row in all_records: writer.writerow(row)
        print(f"\n🎉 총 {len(all_records)}개의 가챠 기록을 '{csv_filename}'에 저장했습니다!\n")
        return True
    else:
        print("📭 저장할 가챠 기록이 없거나 토큰이 만료되었습니다. 게임에서 기록 창을 닫았다가 다시 열어주세요.")
        return False

def analyze_gacha_luck(csv_filename="endfield_gacha_history_all.csv"):
    char_pulls = []
    weap_pulls = []
    
    try:
        with open(csv_filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # 천장을 정확하게 계산하기 위해 과거 시간(gachaTs)부터 오름차순으로 정렬
            rows = sorted(list(reader), key=lambda x: int(x['gachaTs']))
    except FileNotFoundError:
        print(f"❌ '{csv_filename}' 파일을 찾을 수 없습니다.")
        return

    for row in rows:
        rarity = int(row['rarity'])
        name = row.get('charName') if row.get('charName') else row.get('weaponName', '이름 없음')
        pool = row.get('poolName', '')
        
        if row.get('weaponName'):
            weap_pulls.append({'name': name, 'rarity': rarity, 'pool': pool})
        else:
            char_pulls.append({'name': name, 'rarity': rarity, 'pool': pool})

    def calc_pity(pulls_list):
        records = []
        pity = 0
        for p in pulls_list:
            pity += 1
            if p['rarity'] == 6:
                records.append({'name': p['name'], 'pity': pity, 'pool': p['pool']})
                pity = 0
        return records, pity

    char_6stars, current_char_pity = calc_pity(char_pulls)
    weap_6stars, current_weap_pity = calc_pity(weap_pulls)

    CHAR_RATE, WEAP_RATE = 0.016, 0.050

    # ==========================================
    # 캐릭터 헤드헌팅 분석 출력
    # ==========================================
    total_char = len(char_pulls)
    total_char_6 = len(char_6stars)
    if total_char > 0:
        expected_char_6 = total_char * CHAR_RATE
        avg_char_pity = sum(x['pity'] for x in char_6stars) / total_char_6 if total_char_6 > 0 else 0
        char_percentile = (1 - binom.cdf(max(0, total_char_6 - 1), total_char, CHAR_RATE)) * 100

        print("\n" + "=" * 45)
        print("👤 캐릭터 헤드헌팅 운(Luck) 분석 결과")
        print("=" * 45)
        print(f"▶ 총 뽑기 횟수 : {total_char}회")
        print(f"▶ 6성 획득 수  : {total_char_6}명 (공식 확률상 기대치: {expected_char_6:.1f}명)")
        print(f"▶ 평균 6성 천장 : {avg_char_pity:.1f}회 (공식 평균치: 약 62.5회)")
        print(f"▶ 현재 남은 스택 : {current_char_pity} / 80")
        print(f"▶ 상위 % 운    : 상위 {char_percentile:.1f}%")

        if char_percentile < 20: eval_msg = "✨ 축복받은 비틱 계정! 압도적인 행운입니다."
        elif char_percentile < 50: eval_msg = "👍 운이 좋은 편입니다! 남들보다 빠르게 캐릭터를 데려오고 계시네요."
        elif char_percentile <= 70: eval_msg = "⚖️ 정확히 평균적인 운입니다. 평범한 엔드필드 생활 중이네요."
        else: eval_msg = "😭 운이 조금 나빴네요. 천장의 요정이 자주 찾아왔습니다."
        print(f"\n[종합 평가] {eval_msg}")

        print("\n--- 6성 캐릭터 획득 히스토리 ---")
        for r in char_6stars:
            print(f" [{r['pity']:>2}뽑] {r['name']} ({r['pool']})")

    # ==========================================
    # 무기 헤드헌팅 분석 출력
    # ==========================================
    total_weap = len(weap_pulls)
    total_weap_6 = len(weap_6stars)
    if total_weap > 0:
        expected_weap_6 = total_weap * WEAP_RATE
        avg_weap_pity = sum(x['pity'] for x in weap_6stars) / total_weap_6 if total_weap_6 > 0 else 0
        weap_percentile = (1 - binom.cdf(max(0, total_weap_6 - 1), total_weap, WEAP_RATE)) * 100

        print("\n" + "=" * 45)
        print("⚔️ 무기 헤드헌팅 운(Luck) 분석 결과")
        print("=" * 45)
        print(f"▶ 총 뽑기 횟수 : {total_weap}회")
        print(f"▶ 6성 획득 수  : {total_weap_6}개 (공식 확률상 기대치: {expected_weap_6:.1f}개)")
        print(f"▶ 평균 6성 천장 : {avg_weap_pity:.1f}회 (공식 평균치: 약 20.0회)")
        print(f"▶ 현재 남은 스택 : {current_weap_pity} / 40")
        print(f"▶ 상위 % 운    : 상위 {weap_percentile:.1f}%")

        if weap_percentile < 20: eval_msg = "✨ 무기 뽑기의 신! 비정상적으로 훌륭한 운입니다."
        elif weap_percentile < 50: eval_msg = "👍 운이 좋은 편입니다! 무기를 쉽게쉽게 챙겨가시네요."
        elif weap_percentile <= 70: eval_msg = "⚖️ 정확히 평균적인 운입니다. 엔드필드의 확률 공식은 정확하네요!"
        else: eval_msg = "😭 확률의 억까를 조금 당하셨군요... 다음엔 비틱하시길!"
        print(f"\n[종합 평가] {eval_msg}")

        print("\n--- 6성 무기 획득 히스토리 ---")
        for r in weap_6stars:
            print(f" [{r['pity']:>2}뽑] {r['name']} ({r['pool']})")
            
    print("\n" + "=" * 45 + "\n")

if __name__ == "__main__":
    url = extract_gacha_url_from_log()
    if fetch_and_save_all_records(url):
        analyze_gacha_luck()