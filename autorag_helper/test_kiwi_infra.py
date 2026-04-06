try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    res = kiwi.tokenize("민법 제565조(해약금)")
    print("--- [PASS] Kiwi Initialization Successful ---")
    for t in res:
        print(f"Token: {t.form}, Tag: {t.tag}")
except Exception as e:
    print(f"--- [FAIL] Kiwi Error: {e} ---")
    import traceback
    traceback.print_exc()
