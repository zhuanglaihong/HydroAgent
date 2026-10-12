"""One isolated process per operation; state persists on disk between tools."""
import contextlib
import json
import sys

from .budget import json_value
from .service import execute


def main():
    request = json.load(sys.stdin)
    try:
        # Scientific packages may print; stdout is exclusively the JSON protocol.
        with contextlib.redirect_stdout(sys.stderr):
            result = execute(request['workspace'], request['operation'], request['arguments'])
        print(json.dumps(json_value(result), ensure_ascii=False, allow_nan=False))
    except Exception as error:
        print(json.dumps({'success': False, 'error_type': type(error).__name__, 'error': str(error)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
