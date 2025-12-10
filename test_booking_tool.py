# -*- coding: utf-8 -*-
"""
اختبار أداة حجز المعاينة
"""

import requests
import json

# إعدادات الاختبار
BASE_URL = "http://127.0.0.1:8000"
AGENT_ID = "bd0e0d33-c9fb-4da3-a6e7-d2c28ed4bc49"  # Inify

def test_booking():
    """اختبار حجز موعد معاينة"""
    
    # المحادثة
    conversation = [
        {"role": "user", "content": "السلام عليكم"},
        {"role": "assistant", "content": "وعليكم السلام! كيف أقدر أساعدك؟"},
        {"role": "user", "content": "أبي شقة في الرياض"},
        {"role": "assistant", "content": "عندي شقق ممتازة في الرياض. وش ميزانيتك؟"},
        {"role": "user", "content": "500 ألف"},
        {"role": "assistant", "content": "ممتاز! عندي شقة 3 غرف في حي النرجس بـ 480 ألف. تبي تشوفها؟"},
        {"role": "user", "content": "اي ابي اشوفها"},
        {"role": "assistant", "content": "تمام! وش اسمك الكريم ورقم جوالك؟"},
    ]
    
    # رسالة الحجز
    booking_message = "اسمي محمد ورقمي 0555123456 وابي اشوفها بكرة بعد العصر"
    
    print("=" * 60)
    print("🧪 اختبار حجز موعد المعاينة")
    print("=" * 60)
    print(f"\n📱 الرسالة: {booking_message}\n")
    
    # إرسال الطلب
    response = requests.post(
        f"{BASE_URL}/api/v1/chat/public/",
        json={
            "agent_id": AGENT_ID,
            "message": booking_message,
            "chat_history": conversation
        },
        headers={"Content-Type": "application/json"}
    )
    
    print(f"📊 Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n📝 Response Keys: {list(data.keys())}")
        print(f"\n💬 Bot Response:\n{data.get('response', 'No response')}")
        
        if data.get('tool_used'):
            print(f"\n🔧 Tool Used: {data.get('tool_used')}")
        
        if data.get('viewing_booked'):
            print(f"\n✅ VIEWING BOOKED!")
            print(f"   📅 Date: {data['viewing_booked'].get('date')}")
            print(f"   ⏰ Time: {data['viewing_booked'].get('time')}")
            print(f"   🏠 Property: {data['viewing_booked'].get('property')}")
            print(f"   👤 Name: {data['viewing_booked'].get('name')}")
            print(f"   📱 Phone: {data['viewing_booked'].get('phone')}")
        else:
            print("\n❌ No viewing booked in response")
            
        if data.get('lead_created'):
            print(f"\n👤 Lead Created: {data['lead_created']}")
    else:
        print(f"\n❌ Error: {response.text}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_booking()
