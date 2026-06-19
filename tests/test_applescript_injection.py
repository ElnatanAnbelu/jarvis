"""Regression: AppleScript injection → RCE via unescaped iMessage handle/contact
(the P1 finding). send_imessage only escaped the message body; the `handle` was
interpolated raw, and `_looks_like_handle` accepted any string containing '@',
so a poisoned contact could break out of the AppleScript literal into a
`do shell script` line and run arbitrary shell as the user.

These tests pin the escaping + the tightened handle validation. They do NOT
invoke osascript (they verify the sanitization that precedes it).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import control.messages as messages

BREAKOUT = 'x"\ndo shell script "touch /tmp/should_not_exist"\nset y to "z'


def test_osa_str_strips_newlines_and_escapes_quotes():
    esc = messages._osa_str(BREAKOUT)
    assert "\n" not in esc and "\r" not in esc          # no line breakout
    # every double-quote in the output is backslash-escaped
    assert '"' not in esc.replace('\\"', "")


def test_osa_str_escapes_backslashes_before_quotes():
    # a literal backslash must not combine with our added escape to re-open
    esc = messages._osa_str('a\\"; do shell script "x"')
    assert "\n" not in esc
    assert '"' not in esc.replace('\\"', "")


def test_looks_like_handle_rejects_injection_payloads():
    assert messages._looks_like_handle(BREAKOUT) is False
    assert messages._looks_like_handle('a@b" rm -rf ~') is False
    assert messages._looks_like_handle('a@b\nc@d') is False


def test_looks_like_handle_accepts_real_handles():
    assert messages._looks_like_handle("+1 (415) 555-1234")
    assert messages._looks_like_handle("mom@example.com")
    assert messages._looks_like_handle("5551234567")
