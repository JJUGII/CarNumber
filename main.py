from flask import Flask, render_template_string, request
import base64, json, requests, urllib.parse
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5 as PKCS1
from waitress import serve
import logging
from pyngrok import ngrok

app = Flask(__name__)

# 1. ngrok 설정
NGROK_AUTH_TOKEN = "3CUJXAViR5JNbgiTWYvuQnefn4D_4HbPtH4YpVS165JnYb51j"
NGROK_PORT = 5000

# 2. CODEF API 및 인증서 설정
CLIENT_ID = "#CODEF_API_ID"
CLIENT_SECRET = "#CODEF API_SECRET_CODE"
PUBLIC_KEY = "#CODEF_API_KEY"
CERT_PATH = "#인증서 경로 ./cert.der"
KEY_PATH = "#인증서 키 경로 ./key.key"
CERT_PASSWORD = "#인증서 비밀번호"
IDENTITY = "#주민번호"

# 3. 로깅 및 유틸리티 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('waitress')
logger.setLevel(logging.INFO)

def encrypt_rsa(text, public_key):
    key_der = base64.b64decode(public_key)
    key_pub = RSA.import_key(key_der)
    cipher = PKCS1.new(key_pub)
    return base64.b64encode(cipher.encrypt(text.encode("utf-8"))).decode("utf-8")

def get_access_token():
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    res = requests.post("https://oauth.codef.io/oauth/token",
                        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
                        data="grant_type=client_credentials&scope=read")
    return res.json().get("access_token")

# 4. 프론트엔드 HTML
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>차량 제원 조회 시스템</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Malgun Gothic', sans-serif; background: #f4f7f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 95%; max-width: 550px; text-align: center; }
        h2 { color: #2c3e50; margin-bottom: 25px; }

        .plate-container {
            position: relative;
            width: 100%;
            max-width: 500px;
            margin: 0 auto 25px;
            aspect-ratio: 4.8 / 1;
            background-image: url('/static/plate.png'); 
            background-size: cover;
            background-repeat: no-repeat;
            background-position: center;
            border-radius: 5px;
            overflow: hidden;
        }

        .plate-input {
            position: absolute;
            top: 48%; 
            left: 53%; 
            transform: translate(-50%, -50%);
            width: 85%; 
            background: transparent;
            border: none;
            font-family: 'NanumGothic', 'Malgun Gothic', sans-serif; 
            font-size: 68px; 
            font-weight: 700; 
            letter-spacing: 1px; 
            text-align: center;
            outline: none;
            color: #000; 
        }

        @media screen and (max-width: 500px) {
            .plate-input { font-size: 50px; letter-spacing: 1px; width: 85%; }
        }

        .owner-input {
            width: 40%;
            padding: 12px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 16px;
            text-align: center;
        }

        #submitBtn { width: 100%; padding: 15px; background: #3498db; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 18px; }
        #submitBtn:disabled { background: #bdc3c7; }
    </style>
</head>
<body>
    <div class="card">
        <h2>차량 상세 조회</h2>
        <form id="searchForm" onsubmit="return handleFormSubmit(event)">
            <div class="plate-container">
                <input type="text" id="carNo" name="carNo" class="plate-input" 
                       placeholder="123가 1234" oninput="formatPlate(this)" required autocomplete="off">
            </div>
            <input type="text" name="ownerName" class="owner-input" placeholder="소유주 성명 입력" required>
            <button type="submit" id="submitBtn">조회 시작</button>
        </form>
    </div>

    <script>
        function formatPlate(input) {
            let val = input.value.replace(/[^0-9가-힣]/g, '');
            let match = val.match(/([0-9]+)([가-힣])([0-9]+)/);

            if (match) {
                let prefix = match[1];
                let hangeul = match[2];
                let suffix = match[3];
                let totalLen = prefix.length + hangeul.length + suffix.length;
                let space = (totalLen >= 8) ? " " : "  ";
                input.value = prefix + hangeul + space + suffix;
            }
        }

        function handleFormSubmit(event) {
            event.preventDefault();

            const btn = document.getElementById('submitBtn');
            btn.disabled = true;
            btn.innerText = "조회 중...";

            const form = document.getElementById('searchForm');
            const formData = new FormData(form);

            fetch('/search', {
                method: 'POST',
                headers: {
                    'ngrok-skip-browser-warning': 'true'
                },
                body: formData
            })
            .then(response => response.text())
            .then(html => {
                document.open();
                document.write(html);
                document.close();
            })
            .catch(error => {
                console.error('Error:', error);
                alert("조회 중 통신 오류가 발생했습니다.");
                btn.disabled = false;
                btn.innerText = "조회 시작";
            });

            return false;
        }

        window.onpageshow = function(event) {
            if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
                document.getElementById('submitBtn').disabled = false;
                document.getElementById('submitBtn').innerText = "조회 시작";
            }
        };
    </script>
</body>
</html>
"""

# 5. 결과 출력 HTML 생성 함수
def build_result_html(data, car_no):
    spec = data.get("specification", {}).get("info", {}).get("carinfo", {})
    reg = data.get("registration", {})

    brand_nm = str(spec.get("brandNm", "알수없음")).replace("+", " ")
    model_nm = str(spec.get("carClassNm", "알수없음")).replace("+", " ")
    year = str(spec.get("yearType", "-"))

    brand_img = spec.get("brandRepImage", "")
    model_img = spec.get("carClassRepImage", "")

    html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{car_no} 리포트</title>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; background: #f4f7f6; padding: 15px; line-height: 1.6; }}
            .container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            h1 {{ border-bottom: 3px solid #3498db; padding-bottom: 10px; color: #2c3e50; font-size: 20px; }}
            h3 {{ color: #2980b9; margin-top: 25px; border-left: 5px solid #3498db; padding-left: 10px; }}
            .info-header {{ display: flex; align-items: center; background: #ebf5fb; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .brand-logo {{ width: 60px; height: auto; margin-right: 15px; background: white; padding: 5px; border-radius: 5px; }}
            .model-main-img {{ width: 100%; max-width: 400px; display: block; margin: 10px auto; border-radius: 8px; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            th, td {{ padding: 10px; border: 1px solid #eee; text-align: left; }}
            th {{ background: #f8f9fa; width: 35%; color: #7f8c8d; }}
            .color-chip {{ width: 80px; height: auto; border-radius: 4px; border: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>차량 상세 리포트 [{car_no}]</h1>

            <div class="info-header">
                {f'<img src="{brand_img}" class="brand-logo" alt="logo">' if brand_img else ''}
                <div>
                    <div style="font-size: 18px; font-weight: bold;">{brand_nm} {model_nm}</div>
                    <div style="color: #666;">{year}년형 모델</div>
                </div>
            </div>

            {f'<img src="{model_img}" class="model-main-img" alt="model">' if model_img else ''}

            <h3>주요 제원</h3>
            <table>
    """

    if spec:
        for k, v in spec.items():
            if k not in ["gradeList", "brandRepImage", "carClassRepImage"] and not isinstance(v, (dict, list)):
                html += f"<tr><th>{k}</th><td>{str(v).replace('+', ' ')}</td></tr>"

        for grade in spec.get("gradeList", []):
            g_name = str(grade.get("carGradeNm", "")).replace('+', ' ')
            html += f"<tr><th colspan='2' style='background:#d6eaf8; text-align:center;'>세부 트림: {g_name}</th></tr>"
            for gk, gv in grade.items():
                if gk == "clrImageList":
                    html += "<tr><th>외장 색상</th><td>"
                    for clr in gv:
                        c_img = clr.get("imageUrl", "")
                        c_nm = clr.get("clrNm", "").replace("+", " ")
                        html += f'<div style="display:inline-block; margin:5px; text-align:center;">'
                        html += f'<img src="{c_img}" class="color-chip"><br><span style="font-size:10px;">{c_nm}</span>'
                        html += '</div>'
                    html += "</td></tr>"
                elif not isinstance(gv, (dict, list)):
                    html += f"<tr><th>{gk}</th><td>{str(gv).replace('+', ' ')}</td></tr>"

    html += "</table><h3>등록 및 정비 이력</h3><table>"

    if reg:
        history = reg.get("resContentsList", [])
        for item in history:
            date = str(item.get("resRegisterDate", "-"))
            content = str(item.get("resContents", "-")).replace('+', ' ').replace('\n', '<br>')
            html += f"<tr><th style='width:25%'>{date}</th><td>{content}</td></tr>"

    html += """
            </table><br>
            <button onclick='location.reload()' style='width:100%; padding:15px; background:#95a5a6; color:white; border:none; border-radius:6px; font-size: 16px; cursor: pointer;'>새로운 차량 조회하기</button>
        </div>
    </body>
    </html>
    """
    return html

# 6. 라우팅 (Flask API)
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/search', methods=['POST'])
def search():
    car_no = request.form.get('carNo').replace(" ", "")
    owner_name = request.form.get('ownerName')

    try:
        token = get_access_token()
    except Exception as e:
        return f"<h3>Codef 토큰 발급 실패: {e}</h3>"

    url = "https://development.codef.io/v1/kr/etc/complex/used-car/common-info-detail"

    try:
        with open(CERT_PATH, "rb") as f:
            c_file = base64.b64encode(f.read()).decode()
        with open(KEY_PATH, "rb") as f:
            k_file = base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return "<h3>서버 오류: 인증서 파일(.der, .key)을 찾을 수 없습니다.</h3>"

    logging.info(f"[조회 요청] 차량번호: {car_no} / 소유주: {owner_name}")

    payload = {
        "organization": "0001", "certFile": c_file, "keyFile": k_file,
        "certPassword": encrypt_rsa(CERT_PASSWORD, PUBLIC_KEY),
        "certType": "1", "userName": owner_name, "identity": IDENTITY,
        "carNo": car_no, "ownerName": owner_name,
        "displyed": "1", "isIdentityViewYn": "1", "alwaysCarRegistration": "0"
    }

    res = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
    raw_text = urllib.parse.unquote(res.text) if res.text.startswith('%') else res.text
    data = json.loads(raw_text)

    if data.get("result", {}).get("code") == "CF-00000":
        logging.info(f"[조회 성공] {car_no} 데이터 전송 완료")
        return build_result_html(data.get("data", {}), car_no)
    else:
        msg = data.get('result', {}).get('message')
        logging.error(f"[조회 실패] {car_no} 사유: {msg}")
        return f"<h3>조회 실패: {msg}</h3>"

# 7. 서버 실행 및 ngrok 구동
if __name__ == '__main__':
    try:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
        public_url = ngrok.connect(NGROK_PORT).public_url
        print("\n" + "=" * 55)
        print(f"접속 URL: {public_url}")
        print("=" * 55 + "\n")
    except Exception as e:
        print(f"ngrok 시작 중 오류 발생: {e}")

    print(f"서버가 시작되었습니다. - 로컬 주소: http://0.0.0.0:{NGROK_PORT}")
    serve(app, host='0.0.0.0', port=NGROK_PORT, threads=4)