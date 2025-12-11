# -*- coding: utf-8 -*-
"""
اختبار أداة حجز المعاينة
"""

import requests
import json
from datetime import datetime, timedelta

# إعدادات الاختبار
BASE_URL = "http://127.0.0.1:8000"
AGENT_ID = "bd0e0d33-c9fb-4da3-a6e7-d2c28ed4bc49"  # Inify

def test_calendar_api():
    """اختبار API تقويم المعاينة"""
    print("=" * 60)
    print("🗓️ اختبار API تقويم المعاينة")
    print("=" * 60)
    
    # الحصول على أول عقار
    response = requests.get(f"{BASE_URL}/api/v1/properties/agent/{AGENT_ID}/")
    if response.status_code == 200:
        data = response.json()
        if data.get('properties'):
            property_id = data['properties'][0]['id']
            print(f"Property ID: {property_id}")
            
            # الحصول على التقويم
            cal_response = requests.get(f"{BASE_URL}/api/v1/properties/{property_id}/viewing-calendar/")
            if cal_response.status_code == 200:
                cal_data = cal_response.json()
                print(f"\n✅ Calendar API works!")
                print(f"Property: {cal_data.get('property_title')}")
                print(f"Days available: {sum(1 for d in cal_data.get('calendar', []) if d.get('is_available'))}/14")
                
                # عرض أول 3 أيام
                for day in cal_data.get('calendar', [])[:3]:
                    available_slots = [s['time'] for s in day.get('slots', []) if s.get('is_available')]
                    print(f"  {day['day_name']} ({day['date']}): {len(available_slots)} slots available")
            else:
                print(f"❌ Calendar API error: {cal_response.text}")
    else:
        print(f"❌ Properties API error: {response.text}")
    
    print()

def test_booking():
    """اختبار حجز موعد معاينة"""
    
    # حساب تاريخ الغد
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # المحادثة
    conversation = [
        {"role": "user", "content": "السلام عليكم"},
        {"role": "assistant", "content": "وعليكم السلام! كيف أقدر أساعدك؟"},
        {"role": "user", "content": "أبي شقة في جدة"},
        {"role": "assistant", "content": "عندي شقق ممتازة في جدة. وش ميزانيتك؟"},
        {"role": "user", "content": "500 ألف"},
        {"role": "assistant", "content": "ممتاز! عندي شقة 3 غرف في حي الصفا. تبي تشوفها؟"},
        {"role": "user", "content": "اي ابي اشوفها"},
        {"role": "assistant", "content": "تمام! وش اسمك الكريم ورقم جوالك؟"},
    ]
    
    # رسالة الحجز
    booking_message = f"اسمي أحمد ورقمي 0555999888 وابي اشوفها بكرة الساعة 5 العصر"
    
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
    test_calendar_api()
    test_booking()
