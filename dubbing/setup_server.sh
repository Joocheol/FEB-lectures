#!/usr/bin/env bash
# YONSEI-STAT-SERVER 더빙 환경 1회 셋업 스크립트.
#
# 서버 접속 후 (ssh -p 37220 joocheol@165.132.80.36) 아래 두 줄을 실행:
#   git clone -b claude/stoic-shannon-e0wtqh https://github.com/Joocheol/FEB-lectures.git ~/FEB-lectures
#   bash ~/FEB-lectures/dubbing/setup_server.sh
#
# 하는 일: venv 생성 → 의존성 설치 → 모델 가중치(~3GB) 캐시 → CPU 스모크 테스트.
# 전부 로그인 노드에서 실행해도 되는 가벼운 작업이며(테스트 1문장만 CPU 합성),
# 이후 본 합성은 slurm_dub.sbatch로 GPU 노드에 제출한다.
set -euo pipefail

VENV="${DUB_VENV:-$HOME/dub-env}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[1/4] 파이썬 환경 생성: $VENV"
# 이전 실패로 남은 깨진 환경(pip 없음) 정리
if [ -d "$VENV" ] && [ ! -x "$VENV/bin/pip" ]; then
  echo "  깨진 환경 발견 — 삭제 후 재생성"
  rm -rf "$VENV"
fi

if [ ! -x "$VENV/bin/pip" ]; then
  if python3 -m venv "$VENV" 2>/dev/null && [ -x "$VENV/bin/pip" ]; then
    echo "  python3 venv 사용"
  else
    # python3-venv 패키지가 없는 서버(sudo 불가): Miniforge(conda)로 대체
    rm -rf "$VENV"
    echo "  venv 모듈 없음 — Miniforge(conda)로 환경 생성 (sudo 불필요)"
    if command -v conda >/dev/null 2>&1; then
      CONDA="$(command -v conda)"
    else
      if [ ! -x "$HOME/miniforge3/bin/conda" ]; then
        curl -fsSL -o /tmp/miniforge-$USER.sh \
          "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
        bash /tmp/miniforge-$USER.sh -b -p "$HOME/miniforge3"
        rm -f /tmp/miniforge-$USER.sh
      fi
      CONDA="$HOME/miniforge3/bin/conda"
    fi
    "$CONDA" create -y -q -p "$VENV" python=3.11 pip
  fi
fi
"$VENV/bin/pip" install --upgrade pip -q

echo "[2/4] 의존성 설치 (PyTorch 포함, 수 분 소요)"
"$VENV/bin/pip" install -q -r "$HERE/requirements.txt"

echo "[3/4] 모델 가중치 다운로드 (~3GB, 최초 1회)"
"$VENV/bin/python" - <<'EOF'
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
ChatterboxMultilingualTTS.from_pretrained(device="cpu")
print("모델 캐시 완료")
EOF

echo "[4/4] 스모크 테스트 (참조 음성 없이 1문장 CPU 합성)"
"$VENV/bin/python" - <<'EOF'
import torch, torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
wav = m.generate("Setup check complete.", language_id="en")
torchaudio.save("/tmp/dub_smoke_test.wav", wav.cpu(), m.sr)
print("스모크 테스트 통과: /tmp/dub_smoke_test.wav")
EOF

cat <<MSG

셋업 완료. 사용 예:
  sbatch $HERE/slurm_dub.sbatch <대본.txt> <참조.wav> <언어코드> <출력.wav>

GPU 사용 가능 여부 확인:
  sinfo -o "%P %G %D %t"
MSG
