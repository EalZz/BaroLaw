# 1. 환경 설정 (날짜 생성)
NOW=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="backup_$NOW"

# 2. 윈도우에서 최신 코드 가져오기 (기존 작업물 덮어쓰기 전 백업 효과)
# (이미 WSL2 폴더에 최신 코드가 있다면 이 단계는 건너뛰셔도 됩니다)
rm -rf ~/voice-chatbot-toy/android/*
cp -r /mnt/c/Users/KSJ/AndroidStudioProjects/voicechatbotct/* ~/voice-chatbot-toy/android/

# 3. 물리적 백업 생성 (backups 폴더 안에 날짜별로 저장)
echo "📂 $BACKUP_NAME 생성 중..."
cp -r ~/voice-chatbot-toy/android ~/voice-chatbot-toy/backups/$BACKUP_NAME

# 4. Git 커밋 및 푸시
git add .
# 메시지는 현재 수정 내용에 맞춰 변경하세요
git commit -m "Update: 안드로이드 최신 반영 (Backup: $BACKUP_NAME)"
git push origin main

echo "✅ 모든 작업이 완료되었습니다!"
echo "📍 백업 위치: ~/voice-chatbot-toy/backups/$BACKUP_NAME"

