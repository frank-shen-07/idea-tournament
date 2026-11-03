#!/usr/bin/env python3
"""Save, check or remove the OpenRouter API key used by run_jobs.py and round.py.

Run it in your own terminal (not through a chat), so the key never enters a conversation:
  python3 openrouter_key.py            # paste the key at a hidden prompt; it is verified, then saved
  python3 openrouter_key.py --check    # is a key set, and does it work? (shows its label and credit, never the key)
  python3 openrouter_key.py --remove   # delete the saved key

The key is saved to ~/.config/openrouter/key, readable only by your user account (folder 700, file 600), the same
way SSH and cloud CLIs store credentials. It is never printed, logged or written to shell history, and it is only
ever sent to openrouter.ai over verified HTTPS. $OPENROUTER_API_KEY, if set, takes precedence over the file.
"""
import getpass, json, os, stat, sys, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_jobs import TLS  # noqa: E402  (verified TLS context, with a CA fallback for python.org builds)

DIR = os.path.expanduser("~/.config/openrouter")
PATH = os.path.join(DIR, "key")
INFO = "https://openrouter.ai/api/v1/key"  # free: returns the key's label, limit and usage, spends nothing


def verify(key):
    """Returns (ok, message). Never includes the key in the message."""
    req = urllib.request.Request(INFO, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=TLS) as r:
            d = json.load(r).get("data", {})
    except urllib.error.HTTPError as e:
        return False, "OpenRouter rejected this key (HTTP %d). Check you copied the whole key." % e.code
    except urllib.error.URLError as e:
        return None, f"could not reach openrouter.ai to check the key ({e.reason})"
    label = d.get("label") or ""
    if not label or label.startswith("sk-") or "..." in label:  # unnamed keys are labelled with a masked key
        label = "unnamed key"
    limit, usage = d.get("limit"), d.get("usage") or 0
    credit = "no spending limit" if limit is None else f"${max(limit - usage, 0):.2f} of ${limit:.2f} limit left"
    return True, f"works: {label}, used ${usage:.2f}, {credit}"


def save(key):
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    os.chmod(DIR, 0o700)
    tmp = PATH + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # created 600, never briefly world-readable
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    os.replace(tmp, PATH)
    os.chmod(PATH, 0o600)


def saved_key():
    if not os.path.exists(PATH):
        return None
    if stat.S_IMODE(os.stat(DIR).st_mode) & 0o077:
        os.chmod(DIR, 0o700)
        print(f"fixed permissions on {DIR} (now 700, only you can list it)")
    mode = stat.S_IMODE(os.stat(PATH).st_mode)
    if mode & 0o077:
        os.chmod(PATH, 0o600)
        print(f"fixed permissions on {PATH} (was {oct(mode)}, now 0o600)")
    return open(PATH).readline().strip() or None


def main():
    a = sys.argv[1:]
    if "--remove" in a:
        if os.path.exists(PATH):
            os.remove(PATH)
            print(f"removed {PATH}")
        else:
            print("no saved key")
        return
    if "--check" in a:
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        src = "$OPENROUTER_API_KEY" if key else PATH
        key = key or saved_key()
        if not key:
            sys.exit("no OpenRouter key set. Run: python3 openrouter_key.py")
        ok, msg = verify(key)
        print(f"key from {src}: {msg}")
        sys.exit(0 if ok else 1)
    if not sys.stdin.isatty():
        sys.exit("Run this in your own terminal: it needs a hidden prompt. Never paste the key into a chat.")
    print("Get a key at https://openrouter.ai/keys (it starts with sk-or-).")
    print("Paste it below and press Enter. Nothing will show while you paste; that is normal.")
    key = getpass.getpass("OpenRouter key: ").strip().strip("'\"")
    if not key:
        sys.exit("nothing entered; no changes made")
    if not key.startswith("sk-or-"):
        sys.exit("that does not look like an OpenRouter key (they start with sk-or-); no changes made")
    ok, msg = verify(key)
    if ok is False:
        sys.exit(msg + " No changes made.")
    if ok is None:
        print(msg + "; saving it anyway, check later with --check")
    save(key)
    print(f"saved to {PATH} (readable only by you). Key {msg}" if ok else f"saved to {PATH} (readable only by you)")


if __name__ == "__main__":
    main()
