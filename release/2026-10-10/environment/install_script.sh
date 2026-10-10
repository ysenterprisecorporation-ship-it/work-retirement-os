#!/usr/bin/env bash
set -eu
cd /workspace/work-retirement-os
if ! PYTHONPATH=/workspace/work-retirement-tools python -c "import PIL; assert PIL.__version__ == '12.3.0'" >/dev/null 2>&1; then
  python -m pip install --upgrade --target /workspace/work-retirement-tools -r requirements-dev.txt
fi
export PYTHONPATH=/workspace/work-retirement-tools${PYTHONPATH:+:$PYTHONPATH}
test -r /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
python -m unittest discover -s qa -p 'test_*.py' -v
