#!/bin/bash
# YONSEI-STAT-SERVER(응용통계학과 Slurm 클러스터)용 더빙 합성 배치 스크립트.
#
# 제출:  sbatch slurm_dub.sbatch <script.txt> <ref.wav> <lang> <out.wav>
# 예:    sbatch slurm_dub.sbatch week01/video1/script_en.txt ref/joocheol_ref.wav en out/w01v1_en.wav
#
# 여러 편을 한 번에 돌리려면 편별로 sbatch를 반복 제출하면 된다 (각각 GPU 1장).
# 자원 한도 초과분은 PENDING으로 대기하므로 몰아서 제출해도 안전하다.
# 급할 때는 #help 채널에 임시 확장을 요청하고 아래 줄의 주석을 해제한다.
##SBATCH --qos=temp
#
#SBATCH --job-name=dub
#SBATCH --partition=brl
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x-%j.out

set -euo pipefail
mkdir -p logs

SCRIPT=${1:?대본 텍스트 파일}
REF=${2:?참조 음성 wav}
LANG_ID=${3:?언어 코드 (en/zh/ja/es/ko ...)}
OUT=${4:?출력 파일}

# 최초 1회: python3 -m venv ~/dub-env && ~/dub-env/bin/pip install -r requirements.txt
VENV=${DUB_VENV:-$HOME/dub-env}

# 모델 가중치(~3GB)는 첫 실행 때 HuggingFace에서 ~/.cache/huggingface로 받는다.
# 계산 노드에서 외부 접속이 안 되면 로그인 노드에서 아래를 먼저 실행해 캐시를 채운다:
#   ~/dub-env/bin/python -c "from chatterbox.mtl_tts import ChatterboxMultilingualTTS as M; M.from_pretrained(device='cpu')"

srun "$VENV/bin/python" "$(dirname "$0")/synthesize.py" \
  --script "$SCRIPT" --ref "$REF" --lang "$LANG_ID" --out "$OUT"
