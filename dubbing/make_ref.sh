#!/usr/bin/env bash
# 강의 동영상에서 보이스 클로닝용 참조 음성을 추출한다.
#
# 사용법: ./make_ref.sh <강의영상.mp4> <시작시각(초)> <길이(초)> <출력.wav>
# 예:     ./make_ref.sh 13-3.mp4 125 15 joocheol_ref.wav
#
# 요령:
#  - 잡음·기침·침묵 없이 또렷하게 말하는 10~20초 구간을 고른다.
#  - 평서문 억양 구간이 과장된 구간보다 전반적 품질이 좋다.
#  - 언어별 더빙에 같은 참조를 써도 되고, 영어 더빙에는 영어 강의
#    (engN-N.mp4) 구간을 쓰면 발음 특성이 더 잘 옮겨진다.
set -euo pipefail

if [ $# -ne 4 ]; then
  grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -12
  exit 1
fi

SRC=$1; START=$2; DUR=$3; OUT=$4

ffmpeg -v error -ss "$START" -t "$DUR" -i "$SRC" \
  -vn -ac 1 -ar 22050 -af "loudnorm=I=-20:TP=-2" "$OUT"

echo "참조 음성 생성: $OUT"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 "$OUT"
