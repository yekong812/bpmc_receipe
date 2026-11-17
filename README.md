# BPMC 행사 지출 관리

[v3 개발 계획서](event_expense_receipt_system_plan_v3.md)를 바탕으로 만든 로컬 웹 애플리케이션입니다. Next.js + TypeScript 프런트엔드, FastAPI + SQLAlchemy + SQLite 백엔드로 구성합니다.

## 구현 기능

- 행사 날짜와 관리기간을 별도 저장, 행사 생성·수정·복제·삭제, 날짜·기간·상태 필터, 정렬·페이지 이동
- 대형 지출내역 모달, 9개 기본 컬럼, 행 추가·복제·선택 삭제·일괄 저장
- 실시간 전체/항목별 합계, 영수증 배분금액 차이 안내·메모, 미저장 경고
- 임시 저장 → 검토중 전환 → 확정 전 검사 → 최종 확정 → 수정 재오픈 → 재확정
- 불변 확정 버전과 원본 이미지 별도 보관, 버전별 Excel/ZIP 다운로드, 변경 이력
- 행사별 항목 이름·색상·순서·활성 상태, 사용 항목 이동 후 삭제, 다른 행사 항목 복사
- Excel 헤더 탐색·사용자 열 매핑·미리보기·검증·항목 매핑/생성/제외·추가/대체
- 서식과 항목 드롭다운을 적용한 `.xlsx` 내보내기, 영수증 목록 시트, 왕복 호환
- 영수증 ZIP 안전 검사, 이미지 원본 저장·미리보기, SHA-256 중복 제외
- OpenAI Responses API 연동: OCR 텍스트 보완 / 영수증 이미지 직접 분석, 사용량·추정 비용·실패 사유 기록
- 선택 설치 PaddleOCR 연동, 영속 작업 ID/진행률 조회, 규칙 기반 날짜·시간·금액 후보 추출
- OCR 결과로 지출 초안 자동 생성, 중복 매칭 후보는 신규 행 생성 보류, 사용자 수정값 재분석 보호
- OCR 원문·추출 이력·사용자 수정값 비교, 사용자 선택으로 후보값 적용
- 추출값 수동 검토, 매칭 후보 제안, 사용자 승인 연결, 다대다 배분액 검증
- 확인한 영수증으로 지출 생성, 거래일시순 `1_5000.png` 형식의 ZIP 다운로드
- Alembic 초기 마이그레이션, 트랜잭션과 버전 검사로 실패·동시 수정 보호

## 로컬 실행

기본 실행은 Node.js 22와 Python 3.11 이상이 필요합니다. **로컬 PaddleOCR까지 사용하려면 Python 3.11 환경을 권장합니다. 외부 LLM의 이미지 분석은 PaddleOCR 없이 사용할 수 있습니다.** 이 작업 환경의 Python 3.14에서는 기본 API를 검증했고 PaddleOCR는 설치하지 않았습니다.

프로젝트 루트에서:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..
./scripts/dev.sh
```

화면: **http://127.0.0.1:3000**  
API 문서: http://127.0.0.1:8000/docs

`venv` 생성 시 `ensurepip`가 없다는 메시지가 나오면 해당 Python 버전의 `venv` 패키지를 먼저 설치하세요. 예: Ubuntu의 `python3.11-venv`.

서버를 각각 실행할 수도 있습니다.

```bash
# 터미널 1 — 프로젝트 루트
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# 터미널 2
cd frontend
npm run dev
```

백엔드 시작 시 마이그레이션을 적용합니다. 별도 샘플 데이터는 주입하지 않습니다. 화면에서 새 행사를 만들어 시작하세요.

환경변수 예시는 [.env.example](.env.example)을 참고하세요. API에 파일로 전달하려면 `uvicorn ... --env-file .env`를 사용합니다. 프런트엔드의 `API_BASE_URL`은 `frontend/.env.local` 또는 프로세스 환경에 설정하고, 운영 빌드에서는 빌드 전에 지정하세요.

## OCR 실행

Python 3.11 가상환경에서:

```bash
.venv/bin/python -m pip install -r backend/requirements-ocr.txt
```

서버를 재시작하고 영수증 관리 탭에서 ZIP 업로드 → 영수증 분석 시작 → 원본과 추출값 검토 → 검토값 저장 → 지출 연결 순서로 진행합니다. 첫 분석 때 모델 다운로드와 초기화가 필요하므로 인터넷 연결이 필요하며, 이후 로컬 OCR를 사용합니다.

엔진 미설치나 분석 실패는 영수증에 사유를 표시하며 수동 입력으로 계속 사용할 수 있습니다. OCR 결과는 항상 사용자 검토를 거칩니다. 날짜·시간은 임의로 채우지 않으며, 결제금액 후보가 여러 개면 확정하지 않습니다. 취소·환불은 검토 대상으로 표시합니다.

작업 진행률·영수증별 결과·수정값·분석 이력은 SQLite에 저장합니다. 서버 재시작 시 실행 중이던 작업은 중단 상태로 표시합니다. 목록에서 저장된 결과를 확인하고 다시 분석할 수 있습니다. OCR 실행은 한 번에 한 작업씩 처리하며 다중 worker 실행은 지원하지 않습니다. 사용자 수정값은 재분석으로 덮어쓰지 않습니다.

## 외부 LLM 연결: OpenAI

**PaddleOCR를 설치하지 않아도 `vision` 모드에서 영수증 이미지를 직접 분석할 수 있습니다.** 추출 대상은 거래 날짜·시간, 상호, 구매 내역, 원화 최종 결제금액입니다. 분석 후 지출 초안을 생성하며 최종 확정은 사용자가 수행합니다.

### 1. API 키와 환경변수 설정

[OpenAI API 키 관리](https://platform.openai.com/api-keys)에서 발급한 키를 준비합니다. 프로젝트 루트의 `.env.example`을 참고해 `.env`를 만드세요. 기존 `.env`가 있으면 아래 항목을 추가·수정합니다.

```bash
# 처음 설정할 때만 실행
cp .env.example .env
```

PaddleOCR 없이 이미지 직접 분석을 사용하는 예시:

```dotenv
RECEIPT_LLM_ENABLED=true
OPENAI_API_KEY=sk-여기에_실제_API_키
OPENAI_MODEL=gpt-4.1-mini
RECEIPT_LLM_MODE=vision
RECEIPT_LLM_ALLOW_IMAGES=true
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=60
```

`.env`는 Git에서 제외됩니다. API 키는 **프로젝트 루트의 서버용 `.env`에만** 넣고 `NEXT_PUBLIC_` 변수나 프런트엔드 코드에 넣지 마세요. 키 값 자체는 상태 API·분석 이력·오류 메시지에 기록하지 않습니다.

### 2. 서버 실행 및 적용

```bash
./scripts/dev.sh
```

개발 스크립트는 루트 `.env`가 있으면 백엔드에 자동 로드합니다. 환경변수를 바꾸면 실행 중인 서버를 종료하고 다시 실행하세요. 서버를 직접 실행할 때는 파일을 명시합니다.

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

Docker Compose도 루트 `.env` 값을 백엔드 환경에 전달하도록 설정되어 있습니다.

```bash
docker compose up --build -d
# .env만 변경한 경우에도 컨테이너 환경 갱신 필요
docker compose up -d --force-recreate backend
```

`vision`은 `INSTALL_OCR=false` 기본 이미지로 동작합니다. `auto/text`에서 로컬 OCR를 사용하려면 `INSTALL_OCR=true docker compose up --build -d`로 설치합니다.

### 3. 화면에서 사용

행사 상세 → **영수증 관리** → ZIP 업로드 → **영수증 분석 시작** 순서로 진행합니다. 탭 상단에서 LLM 활성 여부·모델·모드·키 설정 여부·이미지 전송 허용 여부를 확인할 수 있습니다. `GET /api/health`에서도 키 값 없이 설정 상태를 확인합니다.

분석이 끝나면 추출값과 지출 초안을 검토하세요. 선택한 영수증의 **분석 이력·현재 값 비교**에서 분석 방식, 모델, 입력/출력 토큰, 추정 비용, 오류 사유를 확인할 수 있습니다. 재분석 후보는 이력에 추가되고 사용자가 저장한 값과 기존 지출 행은 자동으로 덮어쓰지 않습니다. 후보를 적용하려면 검토폼으로 가져온 뒤 저장합니다.

### 분석 모드와 환경변수

| 변수 | 기본값 | 의미 |
|---|---|---|
| `RECEIPT_LLM_ENABLED` | `false` | `true`일 때만 외부 API 호출 허용 |
| `OPENAI_API_KEY` | 없음 | 서버용 API 키 |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Responses·구조화 출력 지원 모델. 이미지 분석 시 이미지 입력도 지원해야 함 |
| `RECEIPT_LLM_MODE` | `auto` | 아래 모드 표 참고 |
| `RECEIPT_LLM_ALLOW_IMAGES` | `false` | 이미지 외부 전송을 명시적으로 허용 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | HTTPS API 루트. 다른 주소는 동일한 Responses API 규격을 지원해야 하며 `/responses`는 자동 추가 |
| `OPENAI_TIMEOUT_SECONDS` | `60` | 영수증 1건의 API 응답 제한, 1~300초 |
| `OPENAI_INPUT_USD_PER_MILLION` | 빈 값 | 선택: 입력 100만 토큰당 USD 단가 |
| `OPENAI_OUTPUT_USD_PER_MILLION` | 빈 값 | 선택: 출력 100만 토큰당 USD 단가 |

| 모드 | 동작 | PaddleOCR 필요 여부 |
|---|---|---|
| `vision` | 영수증마다 이미지를 직접 분석. 로컬 OCR 초기화를 건너뜀 | 불필요 |
| `auto` | OCR 필드가 충분하면 외부 호출 생략. 부족하면 OCR 텍스트로 보완. 텍스트가 없으면 허용된 경우 이미지를 분석 | 이미지 허용 시 없어도 동작 |
| `text` | 부족한 OCR 텍스트만 전송. 이미지는 전송하지 않음 | OCR 텍스트를 얻으려면 필요 |

`auto`에서 텍스트가 있지만 읽기 품질이 나쁘면 텍스트만 보완합니다. 원본 이미지를 직접 읽게 하려면 `vision`을 선택하세요. `text` 또는 `auto`에서 `RECEIPT_LLM_ALLOW_IMAGES=false`이면 이미지가 전송되지 않습니다. 이미지 모드에서도 이미지 전송이 차단되어 있으면 분석 사유로 표시합니다.

### 검토·개인정보·비용과 오류 처리

- 외부로 보내는 OCR 텍스트에는 카드/계좌번호 형태의 긴 숫자, 전화번호, 주민등록번호 형태, 이메일에 대한 규칙 기반 마스킹을 적용합니다. 모든 개인정보 패턴을 완벽하게 탐지하는 것은 아닙니다.
- **이미지는 자동 개인정보 마스킹을 보장하지 않습니다.** 이미지 전송을 허용하면 크기와 방향을 보정하고 메타데이터를 제거한 JPEG를 외부 API로 전송합니다. 원본 파일은 로컬에 유지합니다.
- Responses 요청에는 `store=false`를 사용합니다. 이것이 제공자의 전체 로그·보관 정책을 변경하거나 무보관을 보장하는 의미는 아닙니다.
- JSON 스키마와 서버 검증을 적용합니다. 날짜·시간·금액이 불명확하면 빈 값으로 남기고, 시간이 없을 때 자정을 채우지 않습니다. 외화/불명 통화는 원화 금액으로 확정하지 않습니다. 취소·환불도 사용자 검토가 필요합니다.
- 인증 실패, 사용량 제한, 타임아웃, 응답 거절·미완료·형식 오류는 영수증 검토 사유와 분석 이력에 남기고 다음 영수증 처리를 계속합니다. API 응답 본문의 원문 오류나 API 키를 사용자 오류 메시지에 노출하지 않습니다.
- 자동 재시도는 하지 않습니다. 재분석 버튼을 다시 누르면 추가 API 호출이 발생할 수 있습니다. 기본 응답 출력 제한은 1,600토큰입니다.
- 입력/출력 토큰은 제공자가 반환한 사용량을 기록합니다. 단가 두 개를 설정하면 `(입력 토큰 × 입력 단가 + 출력 토큰 × 출력 단가) / 1,000,000`으로 USD 추정치를 기록합니다. 단가 미설정 시 비용은 미산정으로 표시합니다. 캐시 할인·세금 등을 반영한 청구 금액과는 다를 수 있습니다.

구현 규격은 공식 [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create), [구조화 출력](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [GPT-4.1 mini 모델 설명](https://developers.openai.com/api/docs/models/gpt-4.1-mini)을 참고했습니다. 모델 사용 가능 여부와 단가는 자신의 API 계정에서 확인하세요.

## Docker Compose

```bash
docker compose up --build
# OCR 포함 이미지 (Python 3.11)
INSTALL_OCR=true docker compose up --build
```

화면은 http://127.0.0.1:3000 에서 접근합니다. DB와 원본은 `storage/`에 유지합니다. Compose 파일은 제공하며, 이 개발 환경에서는 Docker 실행을 검증하지 않았습니다. OCR 패키지·모델은 용량이 크고 설치 환경에 따라 시간이 필요합니다.

## v3 저장·확정 사용법

1. 행사 생성 후 영수증 탭에서 ZIP을 업로드하고 OCR 분석을 시작합니다.
2. 분석값을 바탕으로 중복 후보가 아닌 영수증의 지출 초안이 생성됩니다. 분석 실패 시 날짜·금액은 빈 값으로 남습니다.
3. 지출내역과 영수증 탭에서 원본·후보값·현재값을 비교하고 수정합니다. 자동 생성된 초안 행은 `검토 완료`를 체크하세요. 영수증 수정은 `검토값 저장`, 지출 수정은 `임시 저장`으로 반영합니다.
4. `검토중으로 전환` → `최종 확정`에서 필수값과 검토 상태를 확인합니다. 영수증 미첨부·금액 차이는 승인 사유와 확인을 입력한 후 확정할 수 있습니다.
5. 확정 상태에서는 편집이 잠깁니다. `수정 재오픈`하면 이전 확정본을 유지한 채 재수정할 수 있고 재확정 시 다음 버전이 생성됩니다.
6. `변경 이력` 탭에서 확정 버전별 Excel과 ZIP을 다운로드합니다. 재수정 중 목록 총지출은 마지막 확정본을 표시하고 편집 중 금액은 별도 안내합니다.

확정본이 없으면 화면의 내보내기는 `DRAFT_` 파일명으로 초안을 제공합니다. 확정본이 있으면 기본 내보내기는 최신 확정 버전을 사용합니다. API에서 편집 중 초안을 강제로 내보내려면 `?draft=true`, 특정 확정본은 `?version=1`을 사용하세요.

## 업무 규칙

- 금액은 0 이상의 정수 KRW, 총지출은 구매 여부에 관계없이 모든 지출 합계입니다.
- 날짜 연도 생략은 행사 시작 연도를 제안하고 확인을 요구합니다. 빈 날짜는 바로 앞 날짜를 이어받으며 경고를 표시합니다.
- Excel 계산식의 캐시가 없으면 오류로 표시합니다. Excel에서 재계산 후 저장해 가져오세요.
- 원본 Excel이 제공되지 않아 계획서의 9개 컬럼을 기준으로 서식을 구현했습니다. 불명확한 헤더는 사용자가 열 번호를 지정합니다.
- Excel 영수증 번호·총합은 내보내기 참고값입니다. 가져올 때 이미지나 영수증 연결을 자동으로 생성하지 않습니다.
- 영수증 번호는 거래일시순 표시 번호이고 지출 번호·DB ID와 다릅니다.
- 영수증 총합은 연결별 **배분금액** 합계입니다. 한 영수증의 전체 배분액은 최종 결제금액을 초과할 수 없습니다.
- 정리 ZIP은 거래일시·원본 파일명 순으로 정렬합니다. 정상 영수증은 `receipts/`, 시간·금액 미확인은 `review_required/`, 중복 제외는 `excluded/`에 보관하고 `receipts_summary.csv`를 함께 제공합니다. 원본 이미지 바이트를 유지합니다. 날짜만 입력하면 시간을 생성하지 않습니다. 입력 시각은 한국 현지 시각으로 취급하며 시간대가 명시된 값은 한국 시각으로 변환합니다.
- 행사 복제는 행사·항목·지출을 복사합니다. 원본 영수증과 연결은 복사하지 않습니다.
- 행사 삭제는 관련 지출·항목·영수증·이미지 원본을 삭제합니다.
- 업로드: Excel 15MB, ZIP 50MB, 이미지당 15MB, 총 해제 200MB, 이미지 최대 200장. 경로 조작·심볼릭 링크·암호화·고압축률·위장 이미지 파일을 거부합니다.

## 검증

```bash
# 프로젝트 루트
.venv/bin/python -m pytest backend/tests -q

cd frontend
npm run typecheck
npm run build
npx playwright install chromium
# 위의 두 서버가 실행된 상태에서
npm run test:e2e
```

현재 API 통합 테스트 46개와 Chromium 브라우저 시나리오 4개를 검증했습니다. API 테스트는 별도의 임시 DB·파일 저장소를 사용합니다. 브라우저 테스트는 실행 중인 서버에 검증용 행사를 생성하고 성공 시 삭제합니다. 테스트 실패 시 남은 `브라우저 검증 ...` 행사는 화면에서 삭제할 수 있습니다.

## 현재 한계와 후속 작업

- 실제 원본 `.xlsx` 및 실제 영수증 표본이 없어 원본 서식 정밀 대응, OCR 정확도와 50장 처리시간은 아직 검증하지 못했습니다.
- 외부 LLM 호출·응답 검증·사용량 기록은 모의 API로 검증했습니다. 실제 API 키를 이용한 유료 호출과 실제 영수증 정확도는 아직 검증하지 못했습니다.
- 로그인·사용자 권한은 초기 개인용 범위에서 제외했습니다. 기본 실행과 Compose는 로컬 접근용입니다.
- 데이터 백업은 서버를 멈춘 뒤 `storage/` 전체를 복사하세요. 복구도 서버를 멈추고 해당 폴더를 복원합니다.

## 구조

```text
frontend/app/          행사 목록과 스타일
frontend/components/   상세 모달, 항목/Excel/영수증 관리
frontend/lib/          API 클라이언트와 타입
frontend/tests/        브라우저 작업 흐름
backend/app/           API, DB 모델, 확정·이력, Excel/ZIP/OCR 서비스
backend/alembic/       스키마 마이그레이션
backend/tests/         데이터 격리·금액·Excel·영수증·ZIP 보안 테스트
storage/               SQLite DB와 영수증 원본 (버전 관리 제외)
```
