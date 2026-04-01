#!/usr/bin/env python3
"""
Blogger OAuth2 토큰 발급 스크립트
로컬 서버 없이 authorization_code 방식으로 수동 처리
"""
import json
import urllib.parse
import urllib.request

CREDENTIALS_FILE = "credentials.json"

with open(CREDENTIALS_FILE) as f:
    creds_data = json.load(f)["installed"]

CLIENT_ID = creds_data["client_id"]
CLIENT_SECRET = creds_data["client_secret"]
AUTH_URI = creds_data["auth_uri"]
TOKEN_URI = creds_data["token_uri"]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # 코드 화면에 표시되는 방식

SCOPE = "https://www.googleapis.com/auth/blogger https://www.googleapis.com/auth/webmasters"

# 인증 URL 생성
params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": SCOPE,
    "access_type": "offline",
    "prompt": "consent"
}

auth_url = AUTH_URI + "?" + urllib.parse.urlencode(params)

print("=" * 60)
print("아래 URL을 브라우저에서 열어 Google 계정으로 로그인하세요:")
print("=" * 60)
print(auth_url)
print("=" * 60)
print()

code = input("인증 후 표시된 코드를 여기에 붙여넣으세요: ").strip()

# 토큰 교환
data = urllib.parse.urlencode({
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code"
}).encode()

req = urllib.request.Request(TOKEN_URI, data=data, method="POST")
with urllib.request.urlopen(req) as resp:
    token_data = json.loads(resp.read())

print()
print("✅ 토큰 발급 성공!")
print()
print("GitHub Secrets에 등록할 값들:")
print(f"  BLOGGER_CLIENT_ID     = {CLIENT_ID}")
print(f"  BLOGGER_CLIENT_SECRET = {CLIENT_SECRET}")
print(f"  BLOGGER_REFRESH_TOKEN = {token_data['refresh_token']}")
print()

# token.json 저장
with open("token.json", "w") as f:
    json.dump({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": token_data["refresh_token"],
        "token": token_data.get("access_token")
    }, f, indent=2)
print("token.json 저장 완료")
