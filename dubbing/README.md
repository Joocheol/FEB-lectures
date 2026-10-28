# 강의 더빙 파이프라인

교수자 목소리를 클로닝해 번역 대본으로부터 더빙 오디오를 만드는 도구.
LECTURE_PLAN.md 8절(다국어 확장)의 2차 단계를 실행하기 위한 것이다.

- 모델: [Chatterbox Multilingual](https://github.com/resemble-ai/chatterbox)
  (Resemble AI, **MIT 라이선스**, 23개 언어, 제로샷 클로닝 — 별도 학습 불필요)
- 비용: 소프트웨어 $0. 학과 GPU 서버(YONSEI-STAT-SERVER)에서 돌리면 컴퓨팅도 $0.
- 생성 오디오에는 Perth 워터마크(비가청, AI 생성 표식)가 들어간다.

## 흐름

```
대본(script_<lang>.txt) ─┐
참조 음성(ref.wav) ──────┼─→ synthesize.py ─→ 편별 더빙 오디오(wav/m4a)
언어 코드 ───────────────┘        │
                                  └─ 문장별 캐시(.segments/) → 중단·수정 후 재실행 가능
```

1. **참조 음성 만들기** (최초 1회, 언어별 1개 권장)

   드랍박스의 기존 강의 영상에서 깨끗한 10~20초 구간을 추출한다.

   ```bash
   ./make_ref.sh 13-3.mp4 125 15 ref/joocheol_ko.wav
   ```

   영어 더빙에는 영어 강의(engN-N.mp4) 구간을 참조로 쓰면 더 자연스럽다.

2. **대본 준비** — 한 줄 = 한 문장, 빈 줄 = 문단 쉼, `#` = 주석.
   LECTURE_PLAN.md의 제작 규칙대로 한국어 대본(script.md)을 문장 단위로
   써 두었다면, 번역본을 같은 줄 구조로 만들면 된다.

3. **합성**

   ```bash
   python synthesize.py --script week01/video1/script_en.txt \
       --ref ref/joocheol_en.wav --lang en --out out/w01v1_en.m4a
   ```

   - 출력 확장자 `.m4a`는 자동으로 음량 정규화(-16 LUFS, 영상 더빙 표준)까지 된다.
   - 같은 명령을 다시 실행하면 완성된 문장은 건너뛴다(문장 캐시).
   - 특정 문장만 다시 뽑고 싶으면 대본에서 그 문장을 수정(한 글자라도)하거나
     `.segments/`에서 해당 조각 파일을 지우고 재실행한다.
   - 주요 옵션: `--pause`(문장 간격), `--exaggeration`(억양),
     `--cfg-weight`(참조 음성 반영 강도), `--seed`.

## 학과 GPU 서버에서 돌리기

접속(자세한 안내는 서버 Slack #welcome 채널과 yonseiserver.github.io):

```bash
ssh -p 37220 joocheol@165.132.80.36
```

최초 1회 설정:

```bash
python3 -m venv ~/dub-env
~/dub-env/bin/pip install -r requirements.txt
~/dub-env/bin/python -c "from chatterbox.mtl_tts import ChatterboxMultilingualTTS as M; M.from_pretrained(device='cpu')"  # 모델 캐시(~3GB)
```

편별 제출 (GPU 1장, 25분 분량 기준 수 분 내 완료):

```bash
sbatch slurm_dub.sbatch week01/video1/script_en.txt ref/joocheol_en.wav en out/w01v1_en.wav
```

여러 편·여러 언어는 반복 제출하면 Slurm이 알아서 스케줄링한다. 기본 자원
한도를 넘기는 대량 작업은 #help 채널에 임시 확장(`--qos=temp`)을 요청한다.

## 품질 요령

- 참조 음성이 품질의 8할이다. 잡음 없는 또렷한 평서문 구간을 고를 것.
- 긴 숫자·수식은 대본에서 읽는 말로 풀어 쓴다 (예: "d one" / "디 원",
  "시그마 제곱" 등 — 언어별 용어는 `glossary/terms.csv`를 따른다).
- 편당 2~3개 시드로 뽑아 비교 청취 후 선택하면 체감 품질이 올라간다
  (`--seed`만 바꿔 재실행, 출력 이름 구분).
- 최종 영상 합성 시 오디오를 슬라이드 타이밍에 맞추는 작업은 문장 캐시
  조각(`.segments/`) 단위로 편집 프로그램에 얹으면 편하다.

## 알려진 주의점

- `setuptools==80.9.0` 고정 필수 (81+에서 chatterbox의 perth 워터마커가
  `pkg_resources` 부재로 로딩 실패).
- 지원 언어 코드: ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru
  sv sw tr zh. 중국어는 `zh`(간체 발음 기준).
- 한국어(ko)도 지원하지만 1차 한국어 강의는 직접 녹음이 원칙이다
  (LECTURE_PLAN.md). ko 합성은 보충·정정 클립 등 보조 용도로만.
