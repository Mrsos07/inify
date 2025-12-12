# -*- coding: utf-8 -*-
"""
اختبار قيود الوكيل - يجب ألا يجيب على الأسئلة العامة
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"
AGENT_ID = "bd0e0d33-c9fb-4da3-a6e7-d2c28ed4bc49"

def test_restriction(question):
    """اختبار سؤال واحد"""
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/public/",
        json={
            "agent_id": AGENT_ID,
            "message": question,
            "chat_history": []
        },
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        return data.get('response', 'No response')
    return f"Error: {response.status_code}"

print("=" * 60)
print("اختبار قيود الوكيل")
print("=" * 60)

# أسئلة يجب أن يرفض الإجابة عليها
off_topic_questions = [
    "من هو محمد بن سلمان؟",
    "ماهي الدولة السعودية الاولى؟",
    "كم عدد سكان السعودية؟",
    "ما هي عاصمة فرنسا؟",
    "اكتب لي قصيدة",
]

# أسئلة يجب أن يجيب عليها
on_topic_questions = [
    "ابي شقة",
    "ابي شقة للايجار",
    "ابي شقة للايجار في جدة",
]

print("\n🚫 أسئلة خارج النطاق (يجب رفضها):")
print("-" * 40)
for q in off_topic_questions:
    print(f"\n❓ السؤال: {q}")
    answer = test_restriction(q)
    # التحقق من أن الرد يحتوي على رفض
    is_rejected = "متخصص في العقارات" in answer or "عقار" in answer.lower()
    status = "✅ رفض صحيح" if is_rejected else "❌ أجاب (خطأ!)"
    print(f"💬 الرد: {answer[:150]}...")
    print(f"📊 النتيجة: {status}")

print("\n" + "=" * 60)
print("\n✅ أسئلة عقارية (يجب الإجابة عليها):")
print("-" * 40)
for q in on_topic_questions:
    print(f"\n❓ السؤال: {q}")
    answer = test_restriction(q)
    print(f"💬 الرد: {answer[:200]}...")

print("\n" + "=" * 60)
