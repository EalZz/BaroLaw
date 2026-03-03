"""
test_user_integration.py
==========================
리팩토링된 database.py의 3단계 구조(Profile-Session-ChatMessage)가
실제 user_db와 정상적으로 연동되는지 검증한다.
"""

from database import SessionUser, get_or_create_profile, create_chat_session, save_chat_message, get_session_history, Profile, ChatSession, ChatMessage
import uuid

def run_test():
    print("=" * 50)
    print("User Data Integration Test Start")
    print("=" * 50)

    db = SessionUser()
    try:
        # 1. 프로필 생성 (기기 ID 기반)
        test_uid = "test_device_999"
        print(f"\n[1/4] Profile 생성 테스트 (UID: {test_uid})")
        profile = get_or_create_profile(db, test_uid)
        print(f"  => Profile ID: {profile.profile_id}")

        # 2. 세션 생성 (대화방 생성)
        print(f"\n[2/4] Session 생성 테스트")
        test_query = "중고거래 사기를 당했어요. 어떻게 신고하죠?"
        session = create_chat_session(db, profile.profile_id, first_query=test_query)
        print(f"  => Session ID: {session.session_id}")
        print(f"  => Session Title: {session.title}")

        # 3. 메시지 저장 (질문 & 답변)
        print(f"\n[3/4] Message 저장 테스트")
        # 질문 저장
        save_chat_message(db, session.session_id, role="user", content=test_query)
        # 답변 저장 (이전 pgvector 테스트에서 1위였던 사기죄 조문 ID 864번을 참조했다고 가정)
        ai_ans = "형법 제347조(사기)에 의거하여 신고가 가능합니다. 가까운 경찰서에 연락하세요."
        save_chat_message(db, session.session_id, role="ai", content=ai_ans, ref_type="STATUTE", ref_id=864)
        print("  => 메시지 2건 저장 완료 (참조 조문 ID 포함)")

        # 4. 최종 검증 (DB에서 다시 읽기)
        print(f"\n[4/4] 데이터 무결성 검증")
        history = get_session_history(db, session.session_id)
        
        print("-" * 30)
        for msg in history:
            ref_info = f" [참조: {msg.referenced_type} #{msg.referenced_id}]" if msg.referenced_id else ""
            print(f"[{msg.role.upper()}] {msg.content}{ref_info}")
        print("-" * 30)

        if len(history) == 2 and history[1].referenced_id == 864:
            print("\n✅ TEST SUCCESS: 3단계 연동 및 참조 데이터 저장 확인 완료!")
        else:
            print("\n❌ TEST FAILED: 데이터가 일치하지 않습니다.")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
