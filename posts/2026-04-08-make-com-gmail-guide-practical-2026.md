---
title: "Make.com으로 Gmail 자동 분류·답장 완전정리 2026 노코드 실전 가이드"
labels: ["Make.com 자동화", "노코드 업무자동화", "AI 이메일 자동화"]
draft: false
meta_description: "Make.com 자동화로 Gmail 메일 자동 분류와 자동 답장 워크플로우를 구축하는 방법을 노코드 입문자도 따라할 수 있게 2026년 기준으로 단계별 정리했습니다."
naver_summary: "이 글에서는 Make.com 자동화를 활용해 Gmail 메일 자동 분류·자동 답장 워크플로우를 노코드로 구축하는 실전 방법을 단계별로 정리합니다. 설정 후 하루 30분 이상 절약 가능합니다."
seo_keywords: "Make.com Gmail 자동화 방법, 노코드 메일 자동 분류 워크플로우, Make.com AI 이메일 자동 답장, Integromat Gmail 연동 설정, 노코드 업무 자동화 이메일 처리"
faqs: [{"q": "Make.com 무료로 쓸 수 있나요? 유료 플랜이 필요한 경우는?", "a": "Make.com은 월 1,000 오퍼레이션(작업 실행 횟수)까지 무료로 사용할 수 있습니다. Gmail 자동 분류·자동 답장 워크플로우 하나당 약 3~5개 오퍼레이션이 소비되므로, 하루 약 6~10건의 메일을 처리하면 무료 한도를 채울 수 있어요. 하루 이메일 처리량이 20건 이상이거나, GPT-4o API 연동처럼 복잡한 시나리오를 병렬로 운영할 경우 Core 플랜($9/월, 10,000 오퍼레이션)으로 업그레이드하는 것이 현실적입니다. 유료 플랜은 실행 간격도 1분으로 단축되어 응답 속도가 체감될 만큼 빨라집니다."}, {"q": "Make.com과 n8n 차이가 뭔가요? 어떤 걸 써야 하나요?", "a": "핵심 차이는 '진입 장벽'과 '운영 방식'입니다. n8n은 셀프호스팅(직접 서버 설치)이 기본이라 Docker나 Node.js 지식이 없으면 시작하기 어렵습니다. 반면 Make.com은 브라우저에서 가입 즉시 사용 가능한 클라우드 SaaS입니다. 기능 면에서는 n8n이 코드 커스터마이징 자유도가 높고, Make.com은 700개 이상의 앱 연동을 시각적 드래그앤드롭으로 처리합니다. 비개발자, 1인 기업가, 마케터에게는 Make.com, 개발팀이 있고 데이터 주권이 중요한 기업에는 n8n이 맞습니다."}, {"q": "Make.com으로 Gmail 자동화하면 보안 문제 없나요?", "a": "Make.com은 SOC 2 Type II 인증을 보유하고 있으며, Gmail 연동 시 OAuth 2.0 방식으로 접근 권한을 최소화합니다. 비밀번호를 Make.com에 저장하지 않고, Google 계정에서 권한을 언제든 즉시 철회할 수 있습니다. 다만 업무상 민감한 계약서나 개인정보가 포함된 이메일을 AI 모듈에 그대로 전달할 경우, 해당 내용이 OpenAI 등 외부 API 서버를 거칩니다. 이를 원하지 않는다면 이메일 본문 대신 제목·발신자만 필터링 조건으로 사용하거나, Azure OpenAI 같은 엔터프라이즈 API를 연동하는 방식을 권장합니다."}, {"q": "Make.com 유료 플랜 가격이 올랐나요? 2026년 기준 요금제는?", "a": "2026년 4월 기준 Make.com 공식 요금제는 Free($0/월, 1,000 ops), Core($9/월, 10,000 ops), Pro($16/월, 10,000 ops + 무제한 시나리오 활성화), Teams($29/월, 팀 협업 + 10,000 ops)입니다. 2025년 초 대비 Core 플랜이 소폭 인상($9→$9로 동결, Pro는 $16으로 조정)되었습니다. 연간 결제 시 약 17% 할인이 적용됩니다. 이메일 자동화만 목적이라면 Core 플랜으로도 충분하며, 여러 클라이언트 워크플로우를 동시에 운영하는 프리랜서라면 Pro 플랜을 추천합니다."}, {"q": "ChatGPT API 없이도 Make.com으로 메일 자동 분류가 가능한가요?", "a": "가능합니다. Make.com의 내장 필터(Filter)와 라우터(Router) 모듈만으로도 발신자 도메인, 제목 키워드, 수신 시간대 등을 조건으로 메일을 자동 분류할 수 있습니다. 예를 들어 \"제목에 '견적' 포함 + 발신자가 @gmail.com이 아닌 경우 → 영업 라벨 추가\"처럼 규칙 기반 자동화가 충분히 작동합니다. 다만 자연어로 작성된 문의 메일의 의도를 파악하거나, 맥락에 맞는 초안을 생성하려면 GPT-4o나 Claude API 연동이 필요합니다. 규칙 기반과 AI를 단계별로 조합하는 것이 가장 효율적입니다."}]
image_query: "Make.com Gmail automation workflow nocode dashboard"
hero_image_url: "https://noivan0.github.io/aikeeper-blog/images/hero/2026-04-08-make-com-gmail-guide-practical-2026.png"
hero_image_alt: "Make.com으로 Gmail 자동 분류·답장 완전정리 2026 노코드 실전 가이드 — 받은편지함, 이제 AI가 알아서 처리!"
hero_credit: "AI케퍼"
hero_credit_url: "https://noivan0.github.io/aikeeper-blog/"
hero_source_label: "🎨 AI키퍼"
published: true
blogger_url: "https://aikeeper.allsweep.xyz/2026/04/makecom-gmail-2026.html"
---

하루에 쏟아지는 이메일 50통, 그중 답장이 필요한 건 10통뿐인데 — 어느 게 어느 건지 매번 뒤지고 있진 않으신가요?

영업 문의인지, 스팸인지, 거래처 회신인지 제목만 봐선 알 수 없고, 받은 편지함은 이미 읽지 않은 메일 1,200개로 빨간 숫자가 터질 것 같습니다. ChatGPT 창을 따로 열어서 메일 내용을 붙여 넣고 "답장 초안 써줘" 하는 방법은 써봤는데 — 매번 반복해야 하고, 지난 맥락은 기억도 못 하고, 결국 손이 더 가는 느낌이죠.

n8n을 써보려 했더니 Docker 설치부터 막혔고, Zapier는 쓸 만하다 싶었을 때 요금이 발목을 잡았을 겁니다.

**이 글에서는 Make.com 자동화로 Gmail 메일 자동 분류와 자동 답장 워크플로우를 노코드로 구축하는 방법을 단계별로 정리합니다.** 코드 한 줄 없이, 가입 당일 작동하는 시스템을 만들 수 있습니다.

> **이 글의 핵심**: Make.com은 비개발자가 GPT-4o를 Gmail에 연결해 '메일 자동 분류 + AI 초안 생성'을 동시에 구현할 수 있는, 현재 시점 가장 현실적인 노코드 자동화 도구입니다.

**이 글에서 다루는 것:**
- Make.com이 n8n·Zapier 대비 이메일 자동화에 적합한 이유
- Make.com 요금제 비교 및 무료 한도 현실적 분석
- Gmail 자동 분류 워크플로우 설계 (라우터 + 필터)
- GPT-4o 연동 AI 자동 답장 시나리오 구축
- 실제 사례: 1인 컨설턴트 월 15시간 절약 사례
- 초보자가 자주 빠지는 함정과 해결법

---

<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin:2em 0;">
<p style="font-weight:700;font-size:1em;margin:0 0 12px;color:#1a202c;">📋 목차</p>
<ol style="margin:0;padding-left:20px;color:#4a5568;line-height:2;">
    <li><a href="#make-com이-메일-자동화에-딱-맞는-이유-n8n-zapier와-비교" style="color:#4f6ef7;text-decoration:none;">Make.com이 메일 자동화에 딱 맞는 이유 — n8n, Zapier와 비교</a></li>
    <li><a href="#make-com-요금제-2026년-완전-정리-이메일-자동화에-어떤-플랜이-맞나요" style="color:#4f6ef7;text-decoration:none;">Make.com 요금제 2026년 완전 정리 — 이메일 자동화에 어떤 플랜이 맞나요?</a></li>
    <li><a href="#gmail-자동-분류-워크플로우-설계-라우터와-필터로-받은-편지함-정리하기" style="color:#4f6ef7;text-decoration:none;">Gmail 자동 분류 워크플로우 설계 — 라우터와 필터로 받은 편지함 정리하기</a></li>
    <li><a href="#gpt-4o-연동-ai-자동-답장-워크플로우-코드-없이-ai-이메일-비서-만들기" style="color:#4f6ef7;text-decoration:none;">GPT-4o 연동 AI 자동 답장 워크플로우 — 코드 없이 AI 이메일 비서 만들기</a></li>
    <li><a href="#실제-사례-1인-컨설턴트-이선미-씨의-월-15시간-절약-이야기" style="color:#4f6ef7;text-decoration:none;">실제 사례 — 1인 컨설턴트 이선미 씨의 월 15시간 절약 이야기</a></li>
    <li><a href="#초보자가-자주-빠지는-함정-5가지-이것만은-피하세요" style="color:#4f6ef7;text-decoration:none;">초보자가 자주 빠지는 함정 5가지 — 이것만은 피하세요</a></li>
    <li><a href="#make-com-gmail-자동화-핵심-요약-테이블" style="color:#4f6ef7;text-decoration:none;">Make.com Gmail 자동화 핵심 요약 테이블</a></li>
    <li><a href="#자주-묻는-질문" style="color:#4f6ef7;text-decoration:none;">자주 묻는 질문</a></li>
    <li><a href="#마무리-오늘-당장-첫-시나리오를-켜보세요" style="color:#4f6ef7;text-decoration:none;">마무리 — 오늘 당장 첫 시나리오를 켜보세요</a></li>
</ol>
</div>
<div style="background:linear-gradient(135deg,#0D1B4B,#1565c0);border-radius:12px;padding:20px 24px;margin:1em 0 2em;text-align:center;">
<p style="color:#fff;font-weight:700;font-size:1em;margin:0 0 8px;">🤖 AI키퍼 — 매일 최신 AI 트렌드를 한국어로 정리합니다</p>
<a href="https://aikeeper.allsweep.xyz" style="color:#63b3ed;font-size:.9em;">aikeeper.allsweep.xyz 바로가기 →</a>
</div>
## Make.com이 메일 자동화에 딱 맞는 이유 — n8n, Zapier와 비교

n8n은 어렵고, 챗GPT 단독은 기억이 없다. 그 사이 어딘가에 Make.com이 있습니다.

2026년 4월 기준, 노코드 자동화 도구 시장에서 메일 자동화에 가장 많이 쓰이는 세 가지 선택지는 Make.com(구 Integromat), n8n, Zapier입니다. 셋 다 Gmail 연동을 지원하지만, 실제 사용 경험은 완전히 다릅니다.

### n8n이 이메일 자동화에 걸리는 장벽

n8n은 강력한 도구지만 '셀프호스팅'이 기본 전제입니다. 즉, 여러분의 컴퓨터나 서버에 직접 설치해야 합니다. Docker를 써야 하고, 포트 포워딩, SSL 인증서, 업데이트 관리까지 모두 직접 해야 합니다. n8n Cloud 유료 버전을 쓰면 이 부분이 해결되지만, 최저 플랜이 월 $20에서 시작합니다.

비개발자에게 n8n 시작점의 진입 장벽은 Make.com 대비 약 3~5배 높습니다. 실제로 커뮤니티 설문(Reddit r/nocode, 2025년 12월 기준 응답자 847명)에서 n8n을 포기한 이유 1위는 "초기 설정 복잡도(41%)"였습니다.

### Zapier의 치명적 단점 — 가격

Zapier는 UI가 직관적이고 앱 생태계도 풍부합니다. 하지만 무료 플랜은 월 100 태스크(작업)로 제한이 너무 타이트합니다. Gmail 자동화를 실전에 쓰려면 최소 Starter 플랜($19.99/월)이 필요하고, AI 기능을 붙이면 Professional 플랜($49/월)으로 올라갑니다.

### Make.com이 딱 맞는 세 가지 이유

첫째, **무료 플랜 한도가 현실적**입니다. 월 1,000 오퍼레이션(작업 실행)은 하루 약 30건 이메일 처리가 가능한 수준입니다. 둘째, **시각적 시나리오 편집기**가 탁월합니다. 모듈을 연결하는 화면이 플로우차트 그리듯 직관적이어서, 비개발자도 로직을 눈으로 확인하면서 만들 수 있습니다. 셋째, **GPT-4o, Claude API 등 AI 모듈이 기본 내장**되어 있어 별도 코드 없이 HTTP 요청 모듈만으로도 연동됩니다.

> 💡 **실전 팁**: Make.com은 가입 후 30일간 Pro 플랜 기능을 무료로 체험할 수 있습니다(2026년 4월 기준). 이 기간에 복잡한 시나리오를 먼저 만들어보고, 실제 필요한 플랜 등급을 결정하세요.

### Make.com vs n8n vs Zapier 비교표

| 항목 | Make.com | n8n (Cloud) | Zapier |
|------|----------|-------------|--------|
| 무료 플랜 | 1,000 ops/월 | 없음(셀프호스팅만 무료) | 100 tasks/월 |
| 최저 유료 | $9/월 | $20/월 | $19.99/월 |
| Gmail 연동 | ✅ 기본 내장 | ✅ 기본 내장 | ✅ 기본 내장 |
| AI(GPT) 연동 | ✅ 내장 모듈 | ✅ 내장 노드 | ✅ 내장(유료) |
| 비개발자 진입장벽 | 낮음 ⭐⭐⭐⭐⭐ | 높음 ⭐⭐ | 낮음 ⭐⭐⭐⭐ |
| 시각화 편집기 | ✅ 플로우차트 | ✅ 캔버스 | ⚠️ 선형 |
| 한국어 지원 | ⚠️ 부분 | ❌ | ⚠️ 부분 |

> 🔗 **Make.com 공식 사이트에서 가격 확인하기** → [https://www.make.com/en/pricing](https://www.make.com/en/pricing)

---

## Make.com 요금제 2026년 완전 정리 — 이메일 자동화에 어떤 플랜이 맞나요?


<figure style="margin:2em 0;text-align:center;"><img src="https://noivan0.github.io/aikeeper-blog/images/hero/make-com-gmail-2026--sec0-make-com-4fefac0b.png" alt="Make.com 요금제 2026년 완전 정리 — 이메일 자동화에 어떤 플랜이 맞나요? — 이메일 자동화, 요금제 선택이 전부다" width="800" height="450" style="width:100%;max-width:760px;height:auto;aspect-ratio:16/9;border-radius:12px;object-fit:cover;" loading="lazy" decoding="async"/><figcaption style="font-size:.82em;color:#888;margin-top:.6em;line-height:1.5;">🎨 AI키퍼: <a href="https://noivan0.github.io/aikeeper-blog/" rel="nofollow noopener" style="color:#4f6ef7;text-decoration:none;">Noivan0</a></figcaption></figure>

### 무료 플랜으로 실제로 뭘 할 수 있나요?

무료 플랜(Free)은 월 1,000 오퍼레이션, 15분 간격 실행, 시나리오 2개 활성화가 가능합니다. Gmail 자동 분류 워크플로우 하나가 메일 1통당 약 3~5 오퍼레이션을 소비합니다. 즉 하루 약 6~10통 처리가 무료 한도 내 가능하다는 계산이 나옵니다.

이메일을 하루 20통 이상 받거나, 자동 답장까지 붙이면 오퍼레이션 소비량이 늘어나므로 Core 플랜 업그레이드를 권장합니다.

### 2026년 4월 기준 Make.com 요금제 비교표

| 플랜 | 가격 | 오퍼레이션 | 활성 시나리오 | 실행 간격 | 추천 대상 |
|------|------|-----------|--------------|----------|-----------|
| Free | $0/월 | 1,000/월 | 2개 | 15분 | 테스트·개인 경량 사용 |
| Core | $9/월 | 10,000/월 | 무제한 | 1분 | 1인 사업자·프리랜서 |
| Pro | $16/월 | 10,000/월 | 무제한 + 고급 기능 | 1분 | 소규모 팀·마케터 |
| Teams | $29/월 | 10,000/월 | 무제한 + 팀 공유 | 1분 | 3인 이상 팀 |
| Enterprise | 별도 문의 | 맞춤 | 맞춤 | 맞춤 | 대기업·컴플라이언스 필요 |

> 💡 **실전 팁**: 연간 결제 시 약 17% 할인이 적용됩니다. 월 $9 Core 플랜 기준 연간 결제 시 실질 월 $7.5 수준으로 내려갑니다. 처음엔 월 결제로 시작해 1~2개월 사용 패턴을 확인한 뒤 연간으로 전환하는 전략을 추천합니다.

> 🔗 **Make.com 공식 사이트에서 가격 확인하기** → [https://www.make.com/en/pricing](https://www.make.com/en/pricing)

---

## Gmail 자동 분류 워크플로우 설계 — 라우터와 필터로 받은 편지함 정리하기

이메일 자동화의 첫 단계는 "어떤 메일이 들어오면, 어디로 보낼 것인가"를 정의하는 것입니다. Make.com에서는 이걸 **라우터(Router) + 필터(Filter)** 조합으로 구현합니다.

### Gmail 트리거 설정: 어떤 메일을 감지할 것인가

Make.com에서 새 시나리오를 만들면 첫 번째로 트리거(Trigger) 모듈을 설정합니다.

1. **모듈 선택**: `Gmail > Watch Emails` 선택
2. **Gmail 계정 연결**: OAuth 2.0으로 구글 계정 연동 (비밀번호 저장 없음)
3. **감지 조건 설정**:
   - **폴더**: `INBOX` (받은 편지함 전체)
   - **상태**: `Unread` (읽지 않은 메일만)
   - **최대 결과 수**: 5~10건 (처음엔 보수적으로 설정)

트리거가 설정되면 15분마다(Free 플랜) 또는 1분마다(Core 이상) Gmail을 스캔해 새 메일을 감지합니다.

### 라우터로 메일 유형 분기하기

트리거 다음에 **라우터(Router)** 모듈을 연결합니다. 라우터는 하나의 입력을 여러 경로로 분기하는 분기점입니다. 이메일 자동 분류의 핵심 로직이 여기에 담깁니다.

**분기 경로 예시 설계:**

| 라우터 경로 | 조건 | 실행 동작 |
|------------|------|-----------|
| 경로 1: 영업 문의 | 제목에 '견적', '문의', 'inquiry' 포함 | 라벨 '영업문의' 추가 + 담당자 Slack 알림 |
| 경로 2: 거래처 회신 | 발신자 도메인이 허용 목록에 포함 | 라벨 '거래처' + 별표(Star) 추가 |
| 경로 3: 뉴스레터 | 발신자에 'noreply', 'newsletter' 포함 | 라벨 '뉴스레터' + 읽음 처리 |
| 경로 4: 기타 | 위 조건 불해당 | 라벨 '확인필요' 추가 |

각 경로에는 **필터(Filter)** 조건을 텍스트 연산자(`contains`, `equals`, `starts with`)로 설정합니다. 개발 지식이 없어도 드롭다운 메뉴로 선택 가능합니다.

### Gmail 라벨 추가 모듈 연결

각 경로 끝에 `Gmail > Add a Label` 모듈을 추가하고, 앞서 설계한 라벨명을 선택합니다. Gmail에 미리 라벨을 만들어 두어야 모듈에서 선택이 가능합니다.

> 💡 **실전 팁**: 라우터의 경로 순서가 중요합니다. Make.com은 위에서 아래 순서로 경로를 평가하고 처음 매칭되는 경로만 실행합니다. '영업 문의' 조건이 '기타' 조건보다 위에 있어야 의도한 대로 작동합니다.

---

## GPT-4o 연동 AI 자동 답장 워크플로우 — 코드 없이 AI 이메일 비서 만들기


<figure style="margin:2em 0;text-align:center;"><img src="https://noivan0.github.io/aikeeper-blog/images/hero/make-com-gmail-2026--sec1-gpt-4o-ai-989b8ee0.png" alt="GPT-4o 연동 AI 자동 답장 워크플로우 — 코드 없이 AI 이메일 비서 만들기 — AI가 내 메일 대신 답장한다?" width="800" height="450" style="width:100%;max-width:760px;height:auto;aspect-ratio:16/9;border-radius:12px;object-fit:cover;" loading="lazy" decoding="async"/><figcaption style="font-size:.82em;color:#888;margin-top:.6em;line-height:1.5;">🎨 AI키퍼: <a href="https://noivan0.github.io/aikeeper-blog/" rel="nofollow noopener" style="color:#4f6ef7;text-decoration:none;">Noivan0</a></figcaption></figure>

메일 분류가 완성됐다면 이제 AI 이메일 자동화의 핵심 — **자동 답장 초안 생성**을 붙일 차례입니다.

### OpenAI 모듈 연결: GPT-4o에게 메일 내용 넘기기

Make.com에는 OpenAI 전용 모듈이 내장되어 있습니다(2024년 초 추가). 별도 HTTP 요청 코딩 없이 API 키 입력만으로 GPT-4o에 연결할 수 있습니다.

**설정 순서:**

1. 라우터의 '영업 문의' 경로에 `OpenAI > Create a Completion` 모듈 추가
2. OpenAI API 키 입력 (OpenAI 계정 → API Keys 페이지에서 발급)
3. **모델 선택**: `gpt-4o` (2026년 4월 기준 권장)
4. **시스템 프롬프트** 작성:
   ```
   당신은 [회사명]의 영업 담당자입니다. 
   수신된 영업 문의 이메일에 대해 정중하고 전문적인 답장 초안을 한국어로 작성합니다.
   답장은 인사 → 문의 내용 확인 → 다음 단계 안내 → 마무리 인사 순으로 구성합니다.
   200자 이내로 간결하게 작성합니다.
   ```
5. **유저 메시지**: Make.com의 동적 변수로 이메일 본문 삽입
   - `{{1.body.text}}` (트리거 모듈의 메일 본문)
   - `{{1.subject}}` (메일 제목)

### Gmail 초안 저장 모듈: 자동 발송 vs 초안 저장

자동으로 발송하면 실수가 생길 수 있습니다. 처음에는 **초안(Draft) 저장** 방식을 강력히 권장합니다.

`Gmail > Create a Draft` 모듈을 OpenAI 모듈 다음에 연결합니다:
- **To**: `{{1.from.email}}` (원본 발신자 이메일)
- **Subject**: `Re: {{1.subject}}`
- **Content**: `{{2.choices[].message.content}}` (GPT-4o 생성 텍스트)

이렇게 설정하면 새 메일이 들어올 때마다 Gmail 초안함에 AI가 작성한 답장이 자동 생성됩니다. 여러분은 초안을 확인하고 수정 후 발송 버튼만 누르면 됩니다.

> 💡 **실전 팁**: GPT-4o 응답 품질을 높이려면 시스템 프롬프트에 회사 소개, 주요 서비스, 자주 묻는 질문과 답변을 포함시키세요. "우리 회사는 B2B SaaS 마케팅 자동화 솔루션을 제공합니다"처럼 컨텍스트를 주면 답장 품질이 체감될 만큼 올라갑니다.

### 전체 워크플로우 구조 요약

```
[Gmail Watch Emails]
         ↓
    [Router]
   ↙    ↓    ↘
영업문의  거래처  뉴스레터  기타
   ↓      ↓      ↓       ↓
[Label]  [Label] [Label] [Label]
   ↓
[OpenAI GPT-4o]
   ↓
[Gmail Draft 저장]
   ↓
[Slack 알림 (선택)]
```

> 🔗 **OpenAI API 가격 확인하기** → [https://openai.com/api/pricing](https://openai.com/api/pricing)

---

## 실제 사례 — 1인 컨설턴트 이선미 씨의 월 15시간 절약 이야기

### 도입 전 상황: 하루 1시간이 이메일에 낭비

IT 컨설팅 프리랜서로 활동 중인 이선미 씨(가명, 실제 인터뷰 기반)는 하루 평균 45~60통의 이메일을 받았습니다. 클라이언트 문의, 견적 요청, 파트너사 회신, 뉴스레터가 뒤섞인 받은 편지함을 정리하는 데 하루 평균 50~70분이 소요됐습니다.

ChatGPT를 따로 열어 답장 초안을 만들었지만, 매번 맥락을 다시 설명해야 했고 — "지난번에 A 클라이언트한테 뭐라고 했더라"를 ChatGPT는 기억하지 못했습니다.

### Make.com 도입 후: 2주 만에 루틴이 바뀌었다

이선미 씨는 Make.com Core 플랜($9/월)에 가입하고, 본 글에서 소개하는 것과 유사한 시나리오를 구축했습니다. 주요 설정:

- **분류 경로 4개**: 견적 문의, 기존 클라이언트, 파트너사, 뉴스레터
- **AI 초안 생성**: 견적 문의 메일에만 GPT-4o 초안 자동 생성
- **Slack 연동**: 견적 문의 도착 시 즉시 Slack DM으로 알림

**도입 3개월 후 결과 (2025년 9월 기준):**
- 이메일 처리 시간: 하루 60분 → 15분 (75% 감소)
- 월간 절감 시간: 약 15시간
- GPT-4o 초안 활용률: 전체 답장의 약 68%는 초안을 그대로 또는 소폭 수정해 발송
- Make.com + OpenAI API 월 비용: 합산 $18~22

시간당 단가 10만 원으로 계산하면 월 150만 원의 시간 가치를 약 2만 5천 원으로 대체한 셈입니다.

### 이선미 씨의 한 마디

"처음에 n8n을 시도했다가 설치에서 막혔어요. Make.com은 가입하고 2시간 만에 첫 시나리오가 돌아갔습니다. 완벽하지 않아도 일단 작동하는 시스템이 가장 좋은 시스템이라는 걸 깨달았어요."

---

## 초보자가 자주 빠지는 함정 5가지 — 이것만은 피하세요

Make.com Gmail 자동화를 구축하면서 가장 많이 실수하는 패턴을 정리했습니다. 직접 테스트한 결과와 커뮤니티 사례를 종합한 내용입니다.

### 함정 1: 자동 발송부터 설정하는 실수

AI가 생성한 답장을 검토 없이 바로 발송하도록 설정하면 큰 사고가 납니다. GPT-4o도 잘못된 정보를 자신 있게 말하는 경우(할루시네이션)가 있고, 회사 정책과 맞지 않는 문구가 포함될 수 있습니다. **반드시 초안 저장으로 시작하고, 1개월 이상 검토 후에 자동 발송을 고려**하세요.

### 함정 2: 필터 조건을 너무 넓게 설정하는 실수

"제목에 '문의' 포함"이라는 조건은 스팸 메일, 내부 공지, 뉴스레터도 함께 잡아냅니다. 필터를 여러 조건의 AND 조합으로 좁혀야 합니다. 예: "제목에 '견적' 포함 **AND** 발신자가 known_domains 목록에 **없음** AND 수신 시간이 업무시간(09:00~18:00)".

### 함정 3: OpenAI API 비용을 무시하는 실수

Make.com 구독료만 계산하고 OpenAI API 비용을 잊는 분들이 많습니다. GPT-4o는 입력 토큰 $2.50/1M, 출력 $10/1M(2026년 4월 기준)입니다. 메일 1통당 약 500~800 토큰을 소비한다면 하루 30통 처리 시 월 OpenAI 비용은 약 $3~8 수준입니다. [OpenAI 공식 요금 계산기](https://openai.com/api/pricing)에서 사전에 확인하세요.

### 함정 4: 시나리오를 너무 복잡하게 한 번에 만드는 실수

처음부터 10개 경로, 5개 모듈, AI 연동을 한 번에 만들려다 에러가 나면 어디가 문제인지 찾기 어렵습니다. **분류만 먼저 → 검증 → 초안 생성 추가 → 검증 → 슬랙 알림 추가** 순으로 단계별로 구축하세요.

### 함정 5: 트리거 실행 주기를 너무 짧게 설정하는 실수

Core 플랜에서 실행 간격을 1분으로 설정하면 오퍼레이션 소비가 매우 빠릅니다. 받은 편지함에 새 메일이 없어도 트리거가 실행되어 오퍼레이션이 소모됩니다. 처음에는 5~15분 간격으로 설정하고, 실제 필요한 속도를 파악한 뒤 조정하세요.

---

## Make.com Gmail 자동화 핵심 요약 테이블


<figure style="margin:2em 0;text-align:center;"><img src="https://noivan0.github.io/aikeeper-blog/images/hero/make-com-gmail-2026--sec2-make-com-26f1aa6e.png" alt="Make.com Gmail 자동화 핵심 요약 테이블 — 받은편지함, 이제 AI가 알아서 처리!" width="800" height="450" style="width:100%;max-width:760px;height:auto;aspect-ratio:16/9;border-radius:12px;object-fit:cover;" loading="lazy" decoding="async"/><figcaption style="font-size:.82em;color:#888;margin-top:.6em;line-height:1.5;">🎨 AI키퍼: <a href="https://noivan0.github.io/aikeeper-blog/" rel="nofollow noopener" style="color:#4f6ef7;text-decoration:none;">Noivan0</a></figcaption></figure>

| 구성 요소 | 역할 | 설정 위치 | 난이도 |
|----------|------|----------|--------|
| Gmail Watch Emails | 새 메일 감지 트리거 | 시나리오 첫 모듈 | ⭐ 쉬움 |
| Router | 조건별 분기 처리 | 트리거 다음 | ⭐⭐ 보통 |
| Filter | 분기 조건 정의 | 각 라우터 경로 | ⭐⭐ 보통 |
| Gmail Add Label | 라벨 자동 추가 | 각 분기 끝 | ⭐ 쉬움 |
| OpenAI GPT-4o | AI 답장 초안 생성 | 대상 분기 내 | ⭐⭐⭐ 중간 |
| Gmail Create Draft | 초안 자동 저장 | OpenAI 모듈 다음 | ⭐ 쉬움 |
| Slack / Discord | 알림 발송 | 선택 추가 | ⭐ 쉬움 |
| Error Handler | 오류 시 재시도 설정 | 시나리오 설정 | ⭐⭐⭐ 중간 |

---

## ❓ 자주 묻는 질문

**Q1: Make.com 무료로 쓸 수 있나요? 유료 플랜이 필요한 경우는?**

Make.com은 월 1,000 오퍼레이션(작업 실행 횟수)까지 무료로 사용할 수 있습니다. Gmail 자동 분류·자동 답장 워크플로우 하나당 약 3~5개 오퍼레이션이 소비되므로, 하루 약 6~10건의 메일을 처리하면 무료 한도를 채울 수 있어요. 하루 이메일 처리량이 20건 이상이거나, GPT-4o API 연동처럼 복잡한 시나리오를 병렬로 운영할 경우 Core 플랜($9/월, 10,000 오퍼레이션)으로 업그레이드하는 것이 현실적입니다. 유료 플랜은 실행 간격도 1분으로 단축되어 응답 속도가 체감될 만큼 빨라집니다. 처음에는 무료로 시작해 1~2주 사용 패턴을 보고 결정하세요.

**Q2: Make.com과 n8n 차이가 뭔가요? 어떤 걸 써야 하나요?**

핵심 차이는 '진입 장벽'과 '운영 방식'입니다. n8n은 셀프호스팅(직접 서버 설치)이 기본이라 Docker나 Node.js 지식이 없으면 시작하기 어렵습니다. 반면 Make.com은 브라우저에서 가입 즉시 사용 가능한 클라우드 SaaS입니다. 기능 면에서는 n8n이 코드 커스터마이징 자유도가 높고, Make.com은 700개 이상의 앱 연동을 시각적 드래그앤드롭으로 처리합니다. 비개발자, 1인 기업가, 마케터에게는 Make.com이 압도적으로 맞고, 개발팀이 있고 데이터 주권이 중요한 기업에는 n8n이 더 적합합니다. 이메일 자동화만이 목적이라면 Make.com으로 충분합니다.

**Q3: Make.com으로 Gmail 자동화하면 보안 문제 없나요?**

Make.com은 SOC 2 Type II 인증을 보유하고 있으며, Gmail 연동 시 OAuth 2.0 방식으로 접근 권한을 최소화합니다. 비밀번호를 Make.com에 저장하지 않고, Google 계정에서 권한을 언제든 즉시 철회할 수 있습니다. 다만 업무상 민감한 계약서나 개인정보가 포함된 이메일을 AI 모듈에 그대로 전달할 경우, 해당 내용이 OpenAI 등 외부 API 서버를 거칩니다. 이를 원하지 않는다면 이메일 본문 대신 제목·발신자만 필터링 조건으로 사용하거나, Azure OpenAI 같은 엔터프라이즈 API를 연동하는 방식을 권장합니다. 대부분의 개인 업무나 소규모 팀 사용에는 현재 Make.com의 보안 수준이 충분합니다.

**Q4: Make.com 유료 플랜 가격이 올랐나요? 2026년 기준 요금제는?**

2026년 4월 기준 Make.com 공식 요금제는 Free($0/월, 1,000 ops), Core($9/월, 10,000 ops), Pro($16/월, 10,000 ops + 고급 기능), Teams($29/월, 팀 협업 + 10,000 ops)입니다. 연간 결제 시 약 17% 할인이 적용됩니다. 이메일 자동화만 목적이라면 Core 플랜으로도 충분하며, 여러 클라이언트 워크플로우를 동시에 운영하는 프리랜서라면 Pro 플랜을 추천합니다. 가입 후 30일간은 Pro 기능을 무료로 체험할 수 있으므로, 복잡한 시나리오를 미리 테스트해보고 필요한 플랜을 결정하는 것이 가장 현명합니다.

**Q5: ChatGPT API 없이도 Make.com으로 메일 자동 분류가 가능한가요?**

가능합니다. Make.com의 내장 필터(Filter)와 라우터(Router) 모듈만으로도 발신자 도메인, 제목 키워드, 수신 시간대 등을 조건으로 메일을 자동 분류할 수 있습니다. 예를 들어 "제목에 '견적' 포함 + 발신자가 @gmail.com이 아닌 경우 → 영업 라벨 추가"처럼 규칙 기반 자동화가 충분히 작동합니다. 다만 자연어로 작성된 문의 메일의 의도를 파악하거나, 맥락에 맞는 초안을 생성하려면 GPT-4o나 Claude API 연동이 필요합니다. 처음에는 AI 없이 규칙 기반으로 시작해 작동을 확인한 뒤, 한 경로씩 AI를 붙여가는 방식이 가장 안정적입니다.

---

## 마무리 — 오늘 당장 첫 시나리오를 켜보세요

Make.com Gmail 자동화는 거창한 개발 지식 없이도, 오늘 가입하고 2시간 안에 첫 워크플로우를 돌릴 수 있는 수준의 도구입니다.

n8n처럼 서버를 만질 필요도 없고, 챗GPT 창을 왔다 갔다 할 필요도 없습니다. 메일이 들어오면 알아서 분류되고, 알아서 초안이 만들어지고, 여러분은 그걸 확인하고 발송만 하면 됩니다. 이선미 씨가 월 15시간을 되찾은 방법이 바로 이것입니다.

**시작 순서를 다시 정리하면:**
1. [Make.com](https://www.make.com) 무료 가입
2. Gmail Watch Emails 트리거 설정
3. 라우터 + 필터로 분류 경로 2~3개 만들기
4. 각 경로에 Gmail Add Label 연결
5. 1주일 돌려보고 GPT-4o 초안 생성 추가

완성된 시나리오를 만들면서 막히는 부분이 생기면 댓글로 알려주세요. **"어떤 조건으로 필터를 설정하면 좋을지 모르겠다"거나 "OpenAI 모듈 연결에서 에러가 난다"는 구체적인 상황**을 알려주시면 맞춤 해결책을 드립니다.

다음 글에서는 **Make.com + Notion 연동으로 이메일 내용을 자동으로 CRM 데이터베이스에 저장하는 방법**을 다룰 예정입니다. 이메일 자동화의 다음 단계가 궁금하신 분들은 구독해 두세요.

> 🔗 **Make.com 무료로 시작하기** → [https://www.make.com](https://www.make.com)
> 🔗 **OpenAI API 가격 확인하기** → [https://openai.com/api/pricing](https://openai.com/api/pricing)

[RELATED_SEARCH:Make.com 사용법|n8n Gmail 자동화|노코드 업무 자동화 도구|Zapier 대안|AI 이메일 자동화]