# 급식봇을 새 방에 추가하기

급식봇은 **방마다 웹훅(Incoming Webhook) URL이 하나씩** 필요합니다. 채널은 웹훅을 만들 때
고정되므로, 방을 늘리려면 **그 방에서 웹훅을 새로 만들어** URL을 봇 담당자에게 주면 됩니다.
코드는 이미 여러 방 전송을 지원하니, 새 방 담당자는 아래 1번만 하면 됩니다.

## 1. 새 방에서 웹훅 URL 받기 (방 담당자)

1. Mattermost(<https://meeting.ssafy.com>)에서 **메뉴를 보낼 방**에 들어갑니다.
2. 왼쪽 위 **메뉴(⋮ / 격자 아이콘) → 통합(Integrations) → 유입 웹후크(Incoming Webhooks)**
   로 갑니다. 주소로 바로 갈 수도 있습니다: `https://meeting.ssafy.com/<팀이름>/integrations/incoming_webhooks`
3. **웹후크 추가(Add Incoming Webhook)** 를 누르고 이렇게 채웁니다.

   | 항목 | 값 |
   | --- | --- |
   | 제목 | `급식봇` |
   | 설명 | `전기부산 점심 메뉴 자동 전송` |
   | 채널 | **메뉴를 받을 방** |
   | 사용자 이름 잠금 / 프로필 사진 잠금 | 아무렇게나 (이 서버에선 어차피 무시됩니다 — 아래 참고) |

4. **저장**하면 나오는 URL(`https://meeting.ssafy.com/hooks/xxxxxxxxxxxxxxxxxxxxxxxxxx`)을
   복사해 봇 담당자에게 **DM으로** 전달합니다.

### 누구 이름으로 올라가나요

**웹훅을 만든 사람의 이름 + `BOT` 배지**로 올라갑니다. 봇은 `급식봇`이라는 표시 이름을 같이
보내지만(`notify.BOT_NAME`), 이 Mattermost 서버는 integrations 의 username/프로필 덮어쓰기가
**꺼져 있어서** 그 값을 무시합니다. 웹훅 설정의 "사용자 이름 잠금" 체크 여부와 무관합니다.

즉 **새 방 멤버가 웹훅을 만들면 그 사람 이름으로 메뉴가 올라갑니다.** 모든 방을 한 사람 이름으로
통일하려면 그 사람이 웹훅을 전부 만들어야 하고, 비공개 방이면 그 방에 계속 남아 있어야 합니다.

`급식봇` 이름으로 바꾸려면 관리자에게 다음 중 하나를 요청해야 합니다.

1. **System Console → Integrations → Enable integrations to override usernames / profile picture pictures** 를 켜기 (코드 수정 없이 바로 `급식봇` + :bento: 로 바뀝니다)
2. **봇 계정(Bot Account)** 발급 — 웹훅 대신 `MATTERMOST_TOKEN` + 채널 ID 로 API 전송
   (`notify._send_api`). 지금은 채널 하나만 지원하므로 여러 방을 쓰려면 코드를 늘려야 합니다.

> **주의**
> - 웹후크 메뉴가 안 보이면 시스템 관리자가 통합 기능을 막아 둔 것입니다. 관리자에게 요청하세요.
> - **URL은 비밀번호와 같습니다.** 이 URL을 아는 사람은 누구나 그 방에 글을 쓸 수 있으니
>   공개 채널이나 코드에 붙여 넣지 마세요.
> - 이미 만든 웹훅의 채널은 나중에 바꿀 수 있지만, **한 웹훅은 항상 한 방에만** 갑니다.
> - 웹훅은 **만든 사람의 권한에 묶입니다.** 만든 사람이 그 방을 나가거나 계정이 비활성화되면
>   전송이 끊길 수 있으니, 방을 금방 떠날 사람 말고 **오래 남을 멤버**가 만드세요.
> - 봇을 돌리는 담당자는 그 방 **멤버가 아니어도 됩니다.** 전송에는 URL 만 필요합니다.
>   (다만 메시지가 실제로 어떻게 보이는지는 못 보니, 첫날은 방 멤버에게 확인을 받으세요.)

## 2. 봇에 새 방 등록하기 (봇 담당자)

GitHub 저장소 **Settings → Secrets and variables → Actions** 에서
`MATTERMOST_WEBHOOK_URLS` 시크릿에 URL을 **콤마로 이어 붙입니다.**

```
https://meeting.ssafy.com/hooks/기존방URL,https://meeting.ssafy.com/hooks/새방URL
```

- 시크릿이 아직 없으면 **New repository secret** 으로 `MATTERMOST_WEBHOOK_URLS` 를 만들면 됩니다.
- 기존 `MATTERMOST_WEBHOOK_URL`(단수)도 계속 동작합니다. 둘 다 있으면 **합쳐서** 보내고,
  같은 URL이 겹치면 한 번만 보냅니다.
- 워크플로 파일(`.github/workflows/daily-lunch.yml`)은 손댈 필요 없습니다. 이미 두 시크릿을
  모두 읽습니다.

로컬에서 테스트할 때는 `.env` 에 같은 방식으로 넣습니다.

```dotenv
MATTERMOST_WEBHOOK_URLS=https://meeting.ssafy.com/hooks/aaa,https://meeting.ssafy.com/hooks/bbb
```

## 3. 확인

```bash
python -m lunchbot --dry-run   # 메시지만 출력, 전송 안 함
python -m lunchbot             # 실제 전송
```

전송에 성공하면 마지막 줄에 `전송 완료 (webhook 2곳)` 처럼 보낸 방 수가 찍힙니다.
바로 확인하고 싶으면 Actions 탭에서 **Daily lunch menu → Run workflow** 로 수동 실행하세요.
(평일 10:39 KST 정기 실행은 cron-job.org 가 트리거합니다.)

## 동작 방식 / 문제가 생기면

- 방은 **하나씩 순서대로** 보냅니다. 한 방이 실패해도 나머지 방에는 그대로 보내고,
  로그에 `웹훅 일부 전송 실패: #2 ...abc123 — ...` 처럼 **URL 뒤 6자만** 남깁니다.
- 일부라도 실패하면 Actions 잡이 **실패로 표시**됩니다(모두 성공해야 초록불). 로그의 `#번호`는
  시크릿에 적은 순서입니다.
- 모든 방이 실패하면 예외가 나고 잡이 즉시 실패합니다.
- `404` 가 나면 웹훅이 삭제됐거나 URL 오타입니다. 새로 만들어 시크릿을 갱신하세요.

관련 코드: `lunchbot/config.py`(`_env_urls`), `lunchbot/notify.py`(`_send_all_webhooks`).
