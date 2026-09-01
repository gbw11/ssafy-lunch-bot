# SSAFY 급식봇

전기부산 점심 메뉴를 Mattermost **간식먹고노라라** 채널에 자동으로 보냅니다.

## 구조

```
lunchbot/
  __main__.py   CLI + 파이프라인 (메뉴 조회 → 사진 채우기 → 전송)
  config.py     .env 설정 (Settings)
  models.py     StationMenu / DayMenu, 시간 헬퍼
  welplan.py    메뉴 원본 + 당일 사진 1차 소스
  welstory.py   사진 폴백 1 (웰스토리플러스 API)
  mealcloud.py  사진 폴백 2 (welstory-meal.cloud JSON API)
  message.py    Mattermost 마크다운 (사진 크기 통일)
  notify.py     Mattermost 전송 (웹훅 / API 토큰)
```

사진은 **Welplan live API → welstory-meal.cloud → 웰스토리 API** 순으로 채우고, 요리 사진 대신
플레이스홀더가 걸린 코너는 사진 없이 보냅니다. welstory-meal.cloud 는 코너명(`courseName`)이
Welplan 과 어긋나는 날이 있고 코너 순서도 날마다 달라서, 코너명이나 순서가 아니라 **메뉴명**으로
짝지웁니다(`models.menu_key`). 소스마다 원본 크기가 달라서 표에 넣을 때는
`message.py`의 `IMAGE_WIDTH`/`IMAGE_HEIGHT`(기본 240×180)로 전부 같은 크기로 맞춥니다.

## 자동 전송 (GitHub Actions)

GitHub 자체 cron은 지연이 심해서 쓰지 않습니다. 외부 cron(cron-job.org)이 **평일
10:39 KST**에 `daily-lunch.yml`을 `workflow_dispatch`로 트리거하고, 봇이 점심 사진이
올라올 때까지(최대 `PHOTO_WAIT_MINUTES`분) 기다렸다가 대개 **11:00 전후**에 전송합니다.

저장소 Secrets에 `MATTERMOST_WEBHOOK_URL`만 넣으면 동작합니다. 사진은 Welplan 과
welstory-meal.cloud 로 채워지므로 별도 계정이 필요 없습니다. 나머지 설정은 워크플로 파일의
`env` 블록에 있습니다.

웰스토리 API를 **ID/PW 로 로그인하는 경로는 동작하지 않습니다**: `welplus.welstory.com`
앞단의 Imperva/Incapsula 가 `POST /login` 을 봇으로 보고 JSON 대신 자바스크립트 챌린지
HTML(`_Incapsula_Resource`)을 돌려줘서, 아이디·비번이 맞아도 서버가 계정을 확인하는
단계까지 가지 못합니다. 대신 아래처럼 **브라우저 쿠키**를 넣으면 됩니다.

## 웰스토리 원본 사진 (accessToken) — 현재는 못 씁니다

`WELLSTORY_ACCESS_TOKEN` / `WELLSTORY_REMEMBER_ME` 가 있으면 웰스토리 API 를 **폴백보다
먼저** 봅니다(`_photo_sources`). 코드는 준비돼 있지만 **2026-09-01 조사 결과 이 경로는
자동화에 쓸 수 없습니다.** 다시 시도하기 전에 아래를 먼저 읽어 주세요.

- **welplus 는 세션 쿠키를 안 씁니다.** 로그인이 `code: 0` 으로 성공해도 `Set-Cookie` 가
  없고 `JSESSIONID`/`remember-me` 도 안 생깁니다. 토큰은 **로그인 응답의 `authorization`
  헤더**로 옵니다(본문 `data` 는 `null`).
- **그 토큰은 10분짜리입니다.** JWT(HS512, 클레임 `userId`/`hcId`/`authLogin`)를 디코딩하면
  `exp = iat + 600`. 하루 한 번 도는 cron 에 넣을 수 없습니다.
- 게다가 그 토큰을 `requests` 로 `Authorization: Bearer` 에 실어도 `/api/meal` 은
  `wp-error: login` + 빈 본문을 돌려줍니다(유효 시간 안에서 시도해도). `Bearer` 유무,
  `X-Autologin`, 임의 `X-Device-Id`(→ 500) 조합 모두 실패. 브라우저 안에서만 통하는
  무언가(등록된 deviceId 또는 Incapsula 세션)가 더 필요합니다.
- `POST /login` 자체는 **실제 브라우저 페이지 안에서는** WAF 없이 잘 됩니다(같은 오리진
  fetch, 정상 JSON). 반대로 `requests` 로는 자바스크립트 챌린지 HTML만 옵니다.

그래서 **사진은 Welplan live API + welstory-meal.cloud 로만 채우는 게 맞습니다.** 설정을
비워 두면 웰스토리는 아예 시도하지 않습니다. 나중에 앱 트래픽을 떠서 `X-Device-Id` 발급
경로나 장수명 토큰(리프레시)을 찾으면, 값만 채우면 코드는 그대로 동작합니다.

토큰을 다시 확인해 보려면(브라우저 콘솔, welplus 탭에서):

```js
const r = await fetch('/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    username: prompt('아이디'), password: prompt('비밀번호'), 'remember-me': 'true',
  }),
});
const auth = r.headers.get('authorization');   // ← 토큰(10분)
console.log('code =', (await r.json()).code, '| len =', (auth || '').length);
```

`copy(auth)` 를 **한 줄로 따로** 실행해 클립보드에 담고, `.env` 의
`WELLSTORY_ACCESS_TOKEN=` 에 붙여넣은 뒤 `python -m lunchbot --test-welstory` 로 확인합니다.
로그인 실패(`code: -111`)를 반복하면 계정이 30분 잠기고 시도할 때마다 타이머가 갱신되니
재시도하지 마세요.

## 수동 확인

```powershell
pip install -r requirements.txt

python -m lunchbot --dry-run          # 보낼 메시지만 출력
python -m lunchbot --test-welstory    # 웰스토리 사진 URL만 확인
python -m lunchbot --test-mealcloud   # welstory-meal.cloud 사진 URL만 확인
python -m lunchbot --list-restaurants # Welplan 식당 코드 검색
python -m lunchbot                    # 실제 전송
python -m pytest tests -q
```

설정은 `.env.example` 를 `.env` 로 복사해서 채우세요.

## 사진 타이밍

웰스토리는 코너별 실제 배식 사진을 배식 직전(대개 10:30 전후)에 올립니다. 그전까지
점심 메뉴에 걸려 있는 이미지는 전부 같은 플레이스홀더 JPEG입니다. 같은 시각에 조식
사진은 이미 새벽에 올라와 있으므로, 끼니(`mealTimeId`)를 구분하지 않으면 점심 글에
조식 사진이 실립니다. `welplan.course_photos` 가 중식(`mealTimeId=2`)만 남기고,
`PHOTO_WAIT_MINUTES` 동안 사진이 올라오길 기다린 뒤 그래도 없으면 사진 없이 보냅니다.
