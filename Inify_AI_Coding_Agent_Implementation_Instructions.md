# Inify Estate AI — تعليمات التنفيذ للوكيل البرمجي
**الإصدار:** 1.0  
**نوع المستند:** Implementation Specification + Agent Execution Prompt  
**المستودع المستهدف:** `https://github.com/Mrsos07/inify`  
**الهدف:** ترقية المنصة الحالية إلى معمارية V2 الإنتاجية دون إعادة كتابة المشروع أو فقدان التوافق مع وظائفه وبياناته.

> **تعليمات أساسية للوكيل:** هذه وثيقة تكليف بالتنفيذ، لا مجرد توصيات. ابدأ بفحص الكود الفعلي وتحديد ما هو موجود بالفعل، ثم نفّذ الفجوات على مراحل مع اختبارات وإثباتات. لا تدّعِ اكتمال أي مهمة دون شيفرة واختبارات ونتيجة تشغيل. لا تنشر أو تعدّل الإنتاج أو تدوّر أسراراً فعلية دون تصريح من مالك النظام.

---

## 0. رسالة بدء التنفيذ — انسخها للوكيل البرمجي

أنت **Principal Software Architect + Senior Django/AI Engineer + AppSec Engineer + SDET**. مهمتك تطوير مشروع Inify Estate AI الموجود في المستودع، وليس إنشاء مشروع بديل. اقرأ هذا المستند كاملاً، وافحص المستودع وفرعه الحالي، وأنشئ `docs/architecture/current-state-audit.md` وجدول فجوات يربط كل متطلب بالملفات المتأثرة. اعمل وفق المراحل P0 إلى P5. في كل مرحلة: (1) خطة قصيرة، (2) تنفيذ فعلي، (3) Migration آمنة عند الحاجة، (4) اختبارات تلقائية، (5) توثيق، (6) تقرير بنتائج دقيقة وأدلة، (7) انتظر موافقة المالك قبل الانتقال إلى مرحلة جديدة أو تنفيذ تغيير غير قابل للتراجع. لا تستبدل Django بـMicroservices؛ استخدم **Modular Monolith + Unified Agent Runtime + Independent Workers**. لا تحذف وظائف أو واجهات قائمة، ولا تضع مفاتيح حقيقية في المستودع. إذا وجدت تعارضاً بين هذه الوثيقة والكود، سجّله وطبّق الحل الأكثر أماناً مع الحفاظ على التوافق. أوقف التنفيذ عند نقص متطلب مؤثر واطلب قراراً واضحاً.

## 1. مبادئ هندسية غير قابلة للتفاوض

1. **الحفاظ على المشروع:** إعادة هيكلة تدريجية مع المحافظة على عقارات، عملاء، حجوزات، اشتراكات، قنوات واتساب، لوحة التحكم وواجهات التكامل.
2. **المصدر الوحيد للحقيقة:** PostgreSQL لبيانات الأعمال؛ Redis للتخزين المؤقت وChannels؛ Broker متين للمهام؛ لا تعتمد على الذاكرة المحلية لضمان التسليم.
3. **عزل المستأجرين:** كل عملية قراءة أو كتابة تتبع `tenant_id` الموثوق من هوية المستخدم أو قناة موثقة، وليس قيمة يرسلها العميل دون تحقق.
4. **Zero Trust للـLLM:** النموذج يقترح أفعالاً ولا يمنح صلاحيات. جميع الأدوات تتحقق من السياسات والملكية والمدخلات.
5. **Backward compatibility:** نسخ API، ومهاجرات Additive أولاً، وFeature Flags عند تغيير السلوك.
6. **Idempotency + Auditability:** العمليات المؤثرة والدفع والرسائل والحجوزات لا تتكرر عند إعادة المحاولة.
7. **Observability by design:** طلب، مستأجر، محادثة، عملية، استخدام وتكلفة مع إخفاء البيانات الشخصية والأسرار.
8. **لا نجاح وهمياً:** لا تعتبر Docker Build أو استجابة 200 دليلاً على نجاح الأعمال؛ اختبر رحلة المستخدم من البداية للنهاية.

## 2. فحص الواقع الحالي قبل أي تعديل (Mandatory Audit)

افحص `apps/`, إعدادات Django، ملفات `requirements*`، Docker، Render، README، المهاجرات، الاختبارات، ومداخل API. حدد مواضع `PublicChatView`, `get_property_appointments`, `check_admin_access`, `NewraAIService`, `OpenAIService`, StreamPay webhooks, Evolution API webhooks, `CHANNEL_LAYERS`, وملفات البيئة. قد تكون الأسماء تغيّرت؛ ابحث عن الوظيفة بدلاً من افتراض المسار.

أنشئ جدولاً: `Requirement ID | Current implementation | File:line | Gap | Risk | Proposed change | Test | Status`. لا تُكرر مكوّناً يعمل فعلاً. احصر الـEndpoints العامة والداخلية، ومالك كل Route، وطريقة التوثيق، ونوع بياناته. احصر الجداول وعلاقاتها والمهاجرات المتأخرة والمهام الخلفية ومزودي AI.

**مخرجات إلزامية:** `docs/architecture/current-state-audit.md`، `docs/architecture/adr/`، و`docs/implementation/traceability-matrix.md`.

---

## P0 — Security & Tenant Isolation (أولوية مانعة للإطلاق)

### SEC-01 إدارة الأسرار وسلسلة البناء
- امنع إدراج `.env*` الإنتاجية والمفاتيح والاعتمادات في Git وDocker context؛ أبقِ `*.example` بقيم وهمية فقط.
- نفّذ Secret Scanning في CI (مثل Gitleaks) ومنع الدمج عند اكتشاف أسرار.
- استخدم متغيرات البيئة أو Secrets Manager، مع فصل Development/Staging/Production.
- جهّز **خطة** تدوير الأسرار المسربة وتنظيف Git history، وبيّن تأثير Force Push على الفريق؛ لا تنفذ على الريموت أو مفاتيح الإنتاج دون إذن.
- اختبر أن صورة Docker النهائية لا تحتوي أسراراً أو ملفات إعداد إنتاج حساسة.

### SEC-02 توثيق المستخدمين وRBAC
- اجعل Django Authentication وصلاحيات واضحة للأدوار (`platform_admin`, `tenant_owner`, `tenant_admin`, `agent_operator`, `sales`, `read_only`) مع مراعاة الأدوار الحالية.
- أزل الاعتماد على مفتاح إدارة ثابت كبديل عن الهوية والصلاحية؛ نفّذ انتقالاً آمناً، وMFA للإدارة إن أمكن.
- فرض صلاحية كل Endpoint، وليس واجهة المستخدم فقط؛ منع IDOR/BOLA عبر كل موارد النظام.
- أنشئ Permission Matrix واختبارات Allow/Deny لكل دور.

### SEC-03 عزل المستأجرين والمحادثات
- اجعل Tenant Context مشتقاً من جلسة موثوقة أو API Key موثق أو WhatsApp Instance مربوط بالمستأجر.
- جميع استعلامات `Property`, `Lead`, `Conversation`, `Appointment`, `Agent`, `TeamMember`, `Subscription`, `Webhook`, `APIKey`, `Usage` مقيدة بالمستأجر حيث ينطبق.
- للدردشة العامة: إصدار **رمز جلسة عشوائي وموقّع** ومقيد بالمحادثة والوكيل والمستأجر مع صلاحية زمنية؛ لا تسمح باستخدام `conversation_id` وحده كإثبات ملكية.
- امنع الوصول بين الشركات حتى عند معرفة UUID صالح. اختبر تبديل tenant/agent/conversation IDs.
- تأكد من حماية بيانات العملاء في Endpoint المواعيد، ومنع إرجاع الهاتف أو الملاحظات للزوار غير المخولين.

### SEC-04 Webhook Integrity & Replay Protection
- **الدفع:** ارفض Webhook إن لم يكن توقيعه صحيحاً أو سر التحقق غير مهيأ؛ تحقق من raw body وفق مواصفات مزود الدفع، واستخدم event_id فريداً، ولا تفعّل الاشتراك إلا بعد تحقق الحالة والمبلغ والعملة والمرجع من مزود الدفع.
- **واتساب:** تحقّق من التوثيق المتاح في Evolution API/البوابة (توقيع أو سر أو قناة خاصة)، مع فحص مصدر الحدث ومطابقة Instance للمستأجر؛ لا تعتمد على اسم Instance فقط.
- نفّذ replay window، ومخزن أحداث Inbox، وDeduplication بمعرف حدث موثوق.
- لا تسجل جسم Webhook الخام المحتوي على أرقام أو رسائل أو أسرار.

### SEC-05 حماية HTTP وAPI
- أزل `csrf_exempt` من مسارات جلسات المتصفح التي تغيّر الحالة؛ استثنِ فقط Webhooks الموثقة بطريقة مناسبة.
- طبّق CORS allowlist وCSRF Trusted Origins وSecure/HttpOnly/SameSite cookies وHSTS بحسب بيئة النشر.
- لا تمرر API Keys في Query String؛ استخدم Header وHash للمفاتيح المخزنة (مع آلية عرض لمرة واحدة وانتقال للمفاتيح القديمة).
- نفّذ Rate Limits حسب IP وTenant وAgent وAPI Key، وحدود حجم الطلب وملفات الرفع.
- منع SSRF في Outbound Webhooks: السماح بـHTTPS وفق سياسة، منع loopback/private/link-local/metadata IPs، فحص DNS وRedirects وإعادة التحقق عند الاتصال، Timeouts وEgress Policy.
- راجع الأخطاء لتجنب كشف Stack Trace أو أسرار في API responses.

**معايير قبول P0:** جميع اختبارات cross-tenant سلبية؛ لا يستطيع زائر قراءة موعد عميل؛ رفض الدفع المزور؛ رفض Webhook واتساب غير الموثق؛ عدم وجود أسرار داخل Git/Images الجديدة؛ CI Security Checks ناجحة.

---

## P1 — Modular Monolith + Durable Async Infrastructure

### ARC-01 تنظيم الوحدات
احتفظ بـDjango/DRF. افصل المسؤوليات من Views الضخمة إلى خدمات نطاقات واضحة، مع الاحتفاظ بالمسارات الخارجية الحالية قدر الإمكان:
- `identity_tenants` — حسابات، عضويات، أدوار، سياسات.
- `properties` — العقارات، التوافر، الوسائط والبحث.
- `crm` — العملاء، التأهيل، الحالات والتعيين.
- `appointments` — مواعيد المعاينات، التأكيد والإلغاء.
- `conversations` — الرسائل والجلسات وقنوات التفاعل.
- `agents` — إعداد الوكلاء وسياساتهم وأدواتهم.
- `billing` — الاشتراكات والمدفوعات والاستحقاقات.
- `integrations` — Webhooks وPartner APIs وWhatsApp.
- `audit_usage` — أحداث التدقيق والاستهلاك.
هذه **حدود منطقية مقترحة**؛ لا تُعِد تسمية تطبيقات موجودة أو تنقل موديلات بطريقة تكسر المهاجرات دون خطة معتمدة.

### ARC-02 Broker + Worker Pools
- استخدم Celery مع RabbitMQ durable queues **أو** بديلاً موثقاً يضمن المتانة وإعادة المحاولة؛ Redis يبقى Cache/Channels، ويمكن استخدامه Broker فقط بقرار موثق يوضح ضمانات الاسترداد.
- افصل Queues: `ai`, `messaging`, `notifications`, `integrations`, `maintenance`.
- Workers مستقلة قابلة للتوسعة مع timeouts، concurrency limits، backoff+jitter، max retries، وDLQ/failed-job registry وإعادة معالجة يدوية.
- لا تستخدم Threads داخل Web Worker لمعالجة رسائل أو أحداث أعمال مهمة.
- لا تجعل Webhook ينتظر استدعاء LLM؛ أرجع ACK بعد التحقق والتخزين المتين فقط.

### ARC-03 Inbox/Outbox + Exactly-once Business Effects
- Inbox: unique `(provider, external_event_id, tenant_id)` حيث تنطبق هوية الحدث؛ حالات `received/processing/completed/failed`.
- Outbox: حفظ الحدث المطلوب إرساله في **نفس معاملة DB** التي تحفظ أثر الأعمال؛ عامل مستقل ينشره مع retries.
- استهدف **at-least-once delivery + idempotent business effects**، ولا تدّعِ exactly-once delivery على الشبكة.
- امنع تكرار إنشاء Lead/Appointment أو تحصيل الدفع عند إعادة إرسال الحدث.
- سجّل أسباب الفشل وعدد المحاولات وتوقيت المحاولة التالية.

### ARC-04 Realtime + Redis
- استبدل InMemoryChannelLayer في الإنتاج بـRedis-backed Channels Layer مع ASGI deployment وRedis مركزي.
- تحقق من عمل WebSockets عبر نسختين من Web/API وليس عملية واحدة فقط.
- استخدم Cache Keys ذات Tenant Namespace وTTL، ولا تعتمد على Cache Lock وحده لحماية حجوزات DB.

**معايير قبول P1:** إعادة تشغيل Worker أثناء المهمة لا يفقد الحدث؛ إعادة تسليم Webhook لا تكرر أثر الأعمال؛ وصول WebSocket بين نسختين؛ جميع المهاجرات قابلة للتطبيق على DB نظيفة ونسخة بيانات Staging.

---

## P2 — Unified Agent Runtime & AI Governance

### AI-01 توحيد نقطة تنفيذ الوكيل
- أنشئ واجهة خدمة واحدة `AgentRuntime.handle(message, context)` تستخدمها Web Chat وWhatsApp وPartner API.
- ضع Channel Adapters لتوحيد `{tenant, agent, channel, external_message_id, conversation, sender, content, attachments, metadata}`.
- عزل مزود LLM خلف `LLMGateway` يدعم OpenAI حالياً وقابلية إضافة مزود آخر لاحقاً دون تكرار Business Logic.
- ترحيل تدريجي لمسارات `NewraAIService` و`OpenAIService` وأي استدعاءات مباشرة؛ استخدم Feature Flag وShadow Tests عند الحاجة.

### AI-02 Orchestrator & Conversation State
- دورة واضحة: `ingest -> authorize -> load state -> retrieve -> decide -> validate tool -> execute -> respond -> persist -> meter`.
- حدد حدوداً للخطوات والأدوات والوقت والتوكنز؛ مثال مبدئي قابل للضبط: 5 tool calls/turn و30–60 ثانية لعمليات AI غير المتزامنة.
- امنع حلقات الاستدعاء غير المنتهية عبر `max_iterations`, `deadline`, `tool_call_fingerprint` لكشف التكرار، وfallback/human handoff.
- الذاكرة قصيرة المدى مرتبطة بالمحادثة والمستأجر؛ تلخيص سياق المحادثات الطويلة دون تسريب بيانات شركات أخرى.
- اجعل Prompt Templates قابلة للإصدار (versioned) واختبار التغييرات.

### AI-03 Policy Guard & Tool Registry
- سجل أدوات بعقود Typed Inputs/Outputs (Pydantic أو DRF Serializers) وأسماء وإصدارات وصلاحيات.
- أدوات أساسية: `search_properties`, `get_property_details`, `create_or_update_lead`, `get_availability`, `book_viewing`, `cancel_or_reschedule_viewing`, `handoff_to_human`.
- تحقق من Tenant Scope وصلاحية الدور وملكية الموارد **داخل كل Tool Handler**؛ لا تثق بمدخلات LLM.
- أدوات القراءة بلا تأكيد؛ أدوات الكتابة المؤثرة تتطلب تأكيداً صريحاً عند الاقتضاء، مع رموز تأكيد قصيرة العمر وIdempotency Key.
- امنع تسرب System Prompt أو مفاتيح الأدوات في Public Agent Config.
- طبّق Prompt Injection Defense: فصل التعليمات عن محتوى المستخدم/العقار، منع استخدام نصوص الاسترجاع كتعليمات، validation للمخرجات، allowlisted tools، وعدم تمكين LLM من تنفيذ كود أو HTTP عشوائي.

### AI-04 Hybrid Property Retrieval
- نفّذ Structured Filters أولاً (المدينة، الحي، السعر، النوع، المساحة، الحالة، التوافر، Tenant).
- استخدم PostgreSQL full-text + pgvector عند الحاجة، مع Embeddings للحقول المناسبة وإعادة فهرسة عند التعديل.
- Hybrid Ranking: نتائج فلاتر + نصية + دلالية، ثم rerank؛ لا تسمح بظهور عقارات خارج المستأجر أو غير متاحة.
- أرجع Property IDs وأسباب الملاءمة مع منع اختلاق الأسعار والمواصفات.
- أضف fallback إلى Structured Search إذا تعطل Vector Index.

### AI-05 Metering, Evaluation, Human Handoff
- سجل كل LLM call: `tenant_id`, `agent_id`, `conversation_id`, `provider`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_estimate`, `latency`, `status`, `trace_id` دون تخزين أسرار أو PII في Telemetry.
- احسب الاستهلاك عبر كل دورات Tool Calling بما فيها الاستدعاءات المتكررة، مع دعم قواعد تسعير إصدارات النماذج.
- مجموعة تقييم واقعية: أسئلة عقارات، أسعار، تأهيل Lead، حجز، طلبات غير متاحة، Prompt Injection، أخطاء مزود AI، والتحويل إلى موظف.
- حدد قياسات: task completion, grounded answer rate, tool error rate, handoff rate, p50/p95 latency, token cost per resolved conversation.
- دعم Escalation إلى موظف مع سياق ملخص وآمن.

**معايير قبول P2:** نفس الطلب عبر قناتين يمر بالمحرك نفسه؛ لا يمكن للنموذج تنفيذ أداة خارج الصلاحيات؛ لا حلقات غير منتهية؛ لا إجابات تختلق بيانات عقار في اختبارات التقييم؛ كل مكالمة LLM محسوبة.

---

## P3 — Domain Integrity & SaaS Billing

### DOM-01 الحجوزات
- تحقق من نطاق Tenant والعقار والتوافر والدوام والمناطق الزمنية (خزن UTC واعرض Asia/Riyadh عند الحاجة).
- منع Double Booking بقيود DB ومعاملات ذرية (`transaction.atomic`, locks أو exclusion constraint عند فترات متداخلة)؛ لا تكتفِ بـ`exists()` ثم `create()`.
- حالات الحجز: `pending/confirmed/cancelled/completed/no_show` مع سجل انتقالات واضح.
- اختبارات تزامن فعلية: طلبان للحجز نفسه يؤديان إلى حجز واحد فقط.

### DOM-02 CRM & Leads
- تعريف حالات Lead ومصدره وقواعد دمج المكرر ضمن Tenant.
- ربط المحادثة بالعميل والعقار والموعد والموظف المسؤول، مع Audit Trail.
- تأهيل العميل بناءً على معلومات صريحة؛ لا تخزن استنتاجات حساسة دون حاجة.
- دعم البحث والفلاتر والتصدير وفق RBAC وسجلات تدقيق.

### DOM-03 Billing & Entitlements
- تحقق من حالة الدفع الفعلية من المزود عند الحاجة قبل تفعيل الاشتراك؛ منع تكرار تطبيق Webhook.
- عرّف Entitlements صريحة للباقات: عدد الوكلاء، أعضاء الفريق، المحادثات، حدود AI، القنوات والتكاملات.
- نفّذ Usage Quotas ومراقبة التكلفة والتحذير قبل تجاوز الحد، وسياسة graceful degradation.
- افصل السجلات المالية عن `TokenUsage`، واختبر الترقية والتجديد والإلغاء والاسترجاع وانتهاء الاشتراك.
- لا تغيّر الأسعار أو شروط العملاء دون موافقة المالك.

**معايير قبول P3:** اختبار حجز متزامن ناجح؛ لا عمليات دفع مكررة؛ حدود الباقات تعمل من Backend؛ دورة الاشتراك كاملة مغطاة بالاختبارات.

---

## P4 — API, Integrations, Reliability & Operations

### INT-01 Partner API
- OpenAPI 3.0 موثق، API Versioning، Pagination، Filtering، Rate Limits، وIdempotency للـPOST المؤثر.
- مفاتيح API قابلة للإلغاء والتدوير ومحددة النطاق (`scopes`) والمستأجر.
- Webhook Subscriptions: توقيع HMAC مع Timestamp وEvent ID، Retry وDLQ، وإدارة Delivery Logs.

### OPS-01 Observability
- Structured JSON Logs، Metrics وTraces باستخدام OpenTelemetry أو مكافئ؛ `request_id/trace_id/tenant_id/agent_id` مع Redaction.
- لوحات: أخطاء HTTP، queue lag، فشل Webhooks، latency للـAI، تكلفة Tenant، معدلات الحجز، استهلاك الباقات.
- Alerts على فشل الدفع، تراكم DLQ، تأخر الرسائل، فشل مزود AI، أخطاء DB، وارتفاع تكلفة AI.
- Audit Log غير قابل للتعديل بسهولة للأحداث الإدارية والحساسة، مع سياسة احتفاظ وحذف.

### OPS-02 CI/CD & Infrastructure
- Docker Multi-stage minimal images، non-root user، Health/Readiness Checks.
- Staging يشابه الإنتاج؛ Environment-specific settings، migrations آمنة، Rollback/roll-forward plan.
- CI: format/lint, type checks تدريجياً، unit/integration/security tests، dependency scan، secret scan، image scan، build.
- اختبارات تحميل على سيناريوهات متفق عليها؛ لا تخترع ادعاءات throughput أو SLA قبل القياس.
- نسخ احتياطي PostgreSQL وObject Storage، تجربة Restore دورية، وتحديد RPO/RTO بالاتفاق مع المالك.
- Data Retention/Deletion/Export وسياسة خصوصية وامتثال بحسب متطلبات الجهة والتشريعات السعودية ذات الصلة؛ لا تدّعِ شهادة امتثال دون تدقيق.

**معايير قبول P4:** Pipeline أخضر؛ نشر Staging قابل لإعادة الإنتاج؛ تجربة Restore موثقة؛ مراقبة end-to-end؛ OpenAPI محدث؛ اختبارات تحميل مع تقرير فعلي.

---

## P5 — Product Completion & Handover

- رحلة E2E كاملة: إنشاء Tenant → إعداد وكيل → إضافة عقارات → ربط واتساب/Widget → استفسار → ترشيح عقار → إنشاء Lead → حجز → إشعار → متابعة → تقرير استهلاك.
- واجهة إدارة مناسبة للأدوار، وحالات خطأ واضحة، وEmpty States، وOnboarding عملي.
- وثائق تشغيل للمطور وللمشغل: `README`, `ARCHITECTURE`, `DEPLOYMENT`, `RUNBOOK`, `API`, `SECURITY`, `BACKUP_RESTORE`, `TROUBLESHOOTING`.
- قائمة اعتماد للإطلاق وتقرير مقارنة Before/After مع روابط PRs ونتائج الاختبارات وقياسات الأداء الفعلية.
- لا تعلن `production-ready` إلا بعد اجتياز المعايير المتفق عليها وموافقة المالك.

---

## 3. المعمارية المستهدفة (Mermaid)

```mermaid
flowchart TB
  subgraph Channels["قنوات الاستخدام"]
    WA["WhatsApp / Evolution API"]
    WEB["Web Chat Widget"]
    DASH["Dashboard / Backoffice"]
    PARTNER["Partner REST API"]
  end
  subgraph Edge["Edge + Identity"]
    GATE["TLS / WAF / Rate Limits"]
    IAM["Authentication / RBAC / Tenant Context"]
    ADAPT["Channel Adapters / Signed Webhooks / Inbox"]
  end
  subgraph Django["Django Modular Monolith"]
    CONV["Conversation Service"]
    PROP["Property Catalog"]
    CRM["Lead CRM"]
    BOOK["Booking / Availability"]
    BILL["Billing / Entitlements"]
    INT["Integration Hub / Outbox"]
  end
  subgraph Agent["Unified AI Runtime"]
    ORCH["Agent Orchestrator / State"]
    CTX["Context Builder"]
    RET["Hybrid Retrieval"]
    GUARD["Policy Guard"]
    TOOLS["Tool Registry / Execution Gateway"]
    LLM["LLM Gateway"]
    USAGE["Usage Ledger / Evaluation"]
  end
  subgraph Async["Durable Async"]
    BROKER[("RabbitMQ / Durable Broker")]
    AIW["AI Workers"]
    MSGW["Messaging / Webhook Workers"]
    DLQ["Retry / DLQ / Scheduler"]
  end
  subgraph Data["Data Layer"]
    PG[("PostgreSQL / Inbox / Outbox")]
    REDIS[("Redis Cache / Channels")]
    VECTOR[("Full-text / pgvector")]
    OBJECT[("Object Storage")]
  end
  subgraph External["External Providers"]
    MODEL["LLM Provider"]
    PAY["Payment Gateway"]
    MSG["WhatsApp / Email"]
  end
  WA --> ADAPT
  WEB --> GATE
  DASH --> GATE
  PARTNER --> GATE
  GATE --> IAM --> ADAPT
  ADAPT --> CONV
  CONV --> PG
  CONV --> INT
  INT --> PG
  INT --> BROKER
  BROKER --> AIW
  BROKER --> MSGW
  BROKER --> DLQ
  AIW --> ORCH
  ORCH --> CTX
  CTX --> RET --> VECTOR
  ORCH --> GUARD --> TOOLS
  ORCH --> LLM --> MODEL
  ORCH --> USAGE --> PG
  TOOLS --> PROP
  TOOLS --> CRM
  TOOLS --> BOOK
  TOOLS --> BILL
  PROP --> PG
  CRM --> PG
  BOOK --> PG
  BILL --> PG
  PROP --> OBJECT
  BILL --> PAY
  MSGW --> MSG
  CONV --> REDIS
```

### مخطط النشر
- **Web/API Replicas:** Django ASGI/DRF خلف Reverse Proxy مع TLS.
- **Worker Pools:** AI منفصل عن Messaging/Notifications/Integrations.
- **Stateful Services:** PostgreSQL، Redis، Durable Broker، Object Storage، Full-text/Vector Search.
- **Control Plane:** CI/CD، Secrets، Logs/Metrics/Traces، Backup/Restore.
- يمكن بدء النشر بعدد محدود من النسخ ثم التوسع عند ظهور قياسات فعلية؛ لا تفترض الحاجة إلى Kubernetes.

---

## 4. نموذج أحداث وعقود أولية

**Normalized Incoming Message (مثال تصميمي):**
```json
{
  "tenant_id": "resolved-server-side",
  "agent_id": "verified-agent-id",
  "channel": "whatsapp",
  "external_event_id": "provider-event-id",
  "conversation_id": "server-resolved",
  "sender_id": "channel-scoped-id",
  "text": "أبحث عن شقة في الرياض",
  "received_at": "2026-11-03T00:00:00Z",
  "trace_id": "generated-trace-id"
}
```
**ملاحظة:** `tenant_id` و`conversation_id` لا يُوثق بهما إذا جاءا من العميل؛ يُعاد حلهما والتحقق منهما من الخادم.

**أمثلة Domain Events:** `message.received`, `lead.created`, `appointment.booked`, `appointment.cancelled`, `subscription.activated`, `agent.handoff_requested`. لكل حدث `event_id`, `tenant_id`, `schema_version`, `occurred_at`, `correlation_id`, `payload` محدد وخاضع لسياسات خصوصية.

---

## 5. خطة التنفيذ والإبلاغ للمالك

| المرحلة | ترتيب التنفيذ | التحقق المطلوب | نقطة الموافقة |
|---|---|---|---|
| Audit | أولاً | Inventory + Traceability + ADRs | اعتماد خطة التنفيذ |
| P0 | ثانياً | Security Tests + Secrets/Access Review | موافقة قبل تغييرات الأسرار/الريموت |
| P1 | ثالثاً | Durable Jobs + Multi-Replica + DB Migrations | اعتماد البنية التحتية |
| P2 | رابعاً | Agent Evals + Tool Guards + Cost Ledger | اعتماد سياسة الأدوات والنماذج |
| P3 | خامساً | Booking Concurrency + Billing E2E | اعتماد قواعد الأعمال |
| P4 | سادساً | CI/CD + Load/Restore Reports | اعتماد التشغيل |
| P5 | أخيراً | E2E Demo + Handover + Release Checklist | قبول نهائي |

**صيغة تقرير كل مرحلة:**
```text
Phase:
Status: completed / partial / blocked
Implemented:
Changed files / PRs:
Database migrations:
Tests executed (command + pass/fail):
Security checks:
Performance evidence:
Compatibility risks:
Manual verification needed:
Pending decisions:
Next phase:
```

## 6. Definition of Done (معايير الإغلاق النهائي)

- [ ] جميع المتطلبات مرتبطة بملفات وCommits واختبارات.
- [ ] لا توجد أسرار فعلية في الكود أو صور البناء الجديدة.
- [ ] منع الوصول بين المستأجرين والوكالات والمحادثات مثبت باختبارات.
- [ ] توقيعات الدفع وWebhooks والتحقق من Idempotency تعمل.
- [ ] جميع مسارات AI تستخدم Runtime موحداً.
- [ ] Tools تتحقق من الصلاحيات والتأكيد ولا تنفذ إجراءات غير مخولة.
- [ ] مهام الخلفية تتحمل إعادة المحاولة وتعطل Workers دون تكرار أثر الأعمال.
- [ ] الحجوزات آمنة عند التزامن.
- [ ] سجل الاستهلاك يشمل جميع استدعاءات النماذج.
- [ ] Redis Channels يعمل عبر أكثر من نسخة.
- [ ] API موثق، وCI/CD والاختبارات والتتبع فعالة.
- [ ] تجربة استعادة بيانات ناجحة ومثبتة.
- [ ] Demo end-to-end يعمل على Staging.
- [ ] لا توجد تغييرات كاسرة غير معتمدة أو حذف غير مقصود لميزات قائمة.

## 7. تعليمات منع الانحراف للوكيل

- لا تستبدل المشروع بمثال أو Skeleton.
- لا تعِد بإنجاز جميع المراحل في Commit واحد.
- لا تحذف migrations أو تعيد توليدها عشوائياً.
- لا تستخدم `--fake` أو إسقاط جداول لتجاوز مشكلة Migration.
- لا تضع Mock Services في الإنتاج لتبدو الاختبارات ناجحة.
- لا تتجاوز صلاحيات النظام من أجل إتمام تدفق AI.
- لا تنشئ Webhook أو endpoint غير موثق الصلاحيات.
- لا تنشر تغييرات إلى Production ولا تعدّل DNS أو مزود الدفع دون إذن.
- لا تخفِ فشل اختبار؛ سجّل السبب والإصلاح أو العائق.
- عند وجود قرار بين حل سريع وهندسة متينة، قدّم الخيارين مع أثرهما واطلب الموافقة إذا كان مؤثراً.

**الخطوة الأولى المطلوبة الآن:** ~~ابدأ بفحص المستودع وإنتاج Audit + Gap Matrix فقط~~ ✅ تم. **للاستئناف: انتقل إلى القسم 8 أدناه وابدأ من «نقطة الاستئناف».**

---

## 8. سجل التقدم ونقطة الاستئناف (آخر تحديث: 2026-11-03)

> هذا القسم يوثّق ما نُفّذ فعلياً بشيفرة واختبارات، وأين توقف العمل. اقرأه كاملاً قبل أي تعديل جديد.

### 8.1 الحالة العامة

| المرحلة | الحالة |
|---|---|
| Audit | ✅ مكتمل — `docs/architecture/current-state-audit.md`، `docs/implementation/traceability-matrix.md`، `docs/architecture/adr/` (0001–0005) |
| P0 Security & Tenant Isolation | ✅ مكتمل برمجياً ومختبر — يتبقى إجراءات المالك (8.5) |
| P1 Modular Monolith + Durable Async | 🟡 جزئي (Inbox/Outbox وعامل مستقل منجز؛ الباقي في 8.4) |
| P2 Unified Agent Runtime & AI Governance | ⬜ لم يبدأ |
| P3 Domain Integrity & Billing | 🟡 جزئي (تحقق الدفع ومنع تكرار أثره منجز ضمن P0؛ الباقي في 8.4) |
| P4 API, Reliability & Operations | 🟡 جزئي (CI أولي + سجل تدقيق؛ الباقي في 8.4) |
| P5 Product Completion & Handover | ⬜ لم يبدأ |

**الفرع:** `main` — آخر commit مرفوع: `d99d46e`.

| Commit | المحتوى |
|---|---|
| `fb068c4` | P0 الأساسي: الأسرار، عزل المستأجرين، StreamPay، Evolution، مفاتيح API، SSRF، Outbox، الصفحة الرئيسية = المنتج العقاري |
| `61ccae2` | إكمال P0: هوية الأدمن + MFA اختياري، فرض CSRF، RBAC، سجل تدقيق |
| `d99d46e` | معالجة رسائل واتساب الواردة في مهام Outbox دائمة |

**الاختبارات:** 115 اختباراً ناجحاً (`tests/` + `test_whatsapp_fixes.py`).

### 8.2 ما نُفّذ (مع مكان الشيفرة والاختبار)

**SEC-01 الأسرار**
- إلغاء تتبع `.env.production` و`.env.production.secure`؛ `.gitignore` يتجاهل `.env.*` عدا `*.example`؛ `.dockerignore` يستثني `.env*`.
- `.env.production.example` بقيم وهمية؛ `scripts/create_dev_env.py` لإنشاء `.env` محلي بمفاتيح تطوير جديدة.
- CI: `.github/workflows/ci.yml` (Gitleaks على الشجرة والـ commits الجديدة + `check` + `makemigrations --check` + الاختبارات على Python 3.11).
- ⚠️ تدوير الأسرار المسربة وتنظيف تاريخ Git **لم يُنفذ** (يحتاج المالك) — الخطة في `docs/architecture/adr/0003-secrets-and-leak-remediation.md`.

**SEC-02 الهوية وRBAC**
- `services/admin_auth.py` + `check_admin_access`/`admin_login`/`admin_logout` في `apps/core/views.py`: superuser أو مجموعة `platform_admin` أولاً، بيانات البيئة القديمة بمقارنة ثابتة الزمن، `X-Admin-Key` معطل افتراضياً (`ADMIN_LEGACY_KEY_ENABLED`)، TOTP اختياري (`ADMIN_TOTP_SECRET`)، انتهاء جلسة الأدمن (`ADMIN_SESSION_MAX_AGE`)، قفل المحاولات حسب IP موثوق.
- `middleware/role_permission_middleware.py`: دور `viewer` للقراءة فقط، والعضو غير النشط ممنوع من الكتابة.
- `docs/security/permission-matrix.md`. الاختبارات: `tests/test_rbac.py`، `tests/test_admin_csrf_bola.py`.

**SEC-03 عزل المستأجرين**
- مواعيد العقار لمالكه فقط (`get_property_appointments`) — `tests/test_appointments_access.py`.
- رمز جلسة موقّع للدردشة العامة (`apps/chat/views.py` + `widget.html` + `chat-widget.js`) — `tests/test_public_chat_session.py`، ADR-0005.
- WebSocket: مصادقة + تقييد بالمستأجر + `AllowedHostsOriginValidator` — `tests/test_websocket_access.py`.
- منع BOLA في `apps/leads/serializers.py` (`ensure_same_tenant`) وفي نقاط الحجز/العملاء العامة؛ إخفاء أسماء العملاء من ردود التوفر العامة؛ إخفاء الـ System Prompt من الروابط العامة.

**SEC-04 Webhooks**
- StreamPay (`apps/core/views.py::streampay_webhook`): رفض عند غياب السر، نافذة إعادة الإرسال، Inbox على `(event_type, entity_id)`، التفعيل فقط بعد جلب الدفعة من StreamPay والتحقق من الحالة/المبلغ/العملة؛ صفحة العودة لا تعيد استخدام فاتورة — `tests/test_streampay_webhook.py`.
- Evolution: رمز سري لكل Instance في رابط الـ webhook، أمر `secure_whatsapp_webhooks`، علم الانتقال `WHATSAPP_WEBHOOK_LEGACY_ALLOWED`؛ لا تسجيل للجسم الخام — `tests/test_whatsapp_webhook_auth.py`.
- n8n (`WebhookView`): السر إلزامي ومقارنة ثابتة الزمن.

**SEC-05 HTTP/API**
- إزالة `csrf_exempt` من 44 مساراً جلسياً + `static/js/csrf.js` (مضمّن في 40 قالباً) + `middleware/csrf_cookie_middleware.py` + `CSRF_FAILURE_VIEW` بصيغة JSON.
- مفاتيح API: Header فقط، تخزين hash (ترحيل تلقائي للمفاتيح القديمة)، scopes، حد طلبات، `Idempotency-Key` — `tests/test_api_keys.py`.
- `services/rate_limit.py` (حدود على النقاط العامة)، `services/url_safety.py` (SSRF) — `tests/test_outbox_and_ssrf.py`.
- إخفاء نص الأخطاء الداخلية عن العميل واستبدال `print` بالـ logging في views الرئيسية.

**P1/P3/P4 (جزئي)**
- Inbox: `InboundWebhookEvent`؛ Outbox: `OutboxEvent` + `services/outbox.py` + أوامر `run_outbox_worker` و`outbox_requeue` (retries + backoff/jitter + DLQ + استرداد بعد تعطل العامل). القرار: ADR-0004 الخيار C (PostgreSQL Outbox).
- الـ webhooks الصادرة ورسائل واتساب الواردة تعمل عبر Outbox — `tests/test_whatsapp_async.py`.
- `AuditEvent` للإضافة فقط ويسجل عمليات الأدمن.
- حقول قياس إضافية في `TokenUsage` (provider, purpose, conversation_id, prompt_version, latency_ms, status, cost_estimate, trace_id) — **أُضيفت الحقول فقط، لم تُربط بعد بكل استدعاءات LLM**.

**Migrations الجديدة:** `agents/0026_security_inbox_outbox_apikey_metering`، `agents/0027_audit_event` (إضافية فقط).

**أخطاء موجودة سابقاً أُصلحت:** `/api/v1/agents/webhooks/` كان يرجع 500؛ `import os` ناقص في `apps/agents/models.py`.

**تغيير منتج:** الرابط `/` يعرض صفحة المنتج العقاري (`index.html`)، و`/estate/` يحوّل 301 إلى `/`، وحُذف `company_home.html`.

### 8.3 نقطة الاستئناف (ابدأ من هنا بالترتيب)

1. **P1 — بقية الـ threads:** إعادة الاتصال التلقائي للواتساب ما زالت تستخدم `threading.Thread` في `apps/chat/whatsapp_views.py` (حوالي السطر 106) و`apps/core/whatsapp_views.py` (حوالي السطر 510) → حوّلها إلى مهمة Outbox `whatsapp.reconnect` على طابور `messaging`. ملاحظة: `test_whatsapp_fixes.py` يختبر `apps/core/whatsapp_views.whatsapp_webhook` (غير مربوط بـ URL).
2. **P1 — ARC-04:** `CHANNEL_LAYERS` ما زال `InMemoryChannelLayer` (`config/settings.py` حوالي السطر 182) → استخدم `channels_redis` عند وجود `REDIS_URL`.
3. **P1/P4 — Docker:** `Dockerfile` يشغّل gunicorn WSGI كـ root ويشغّل migrate عند كل إقلاع → multi-stage، مستخدم غير root، تشغيل ASGI (daphne/uvicorn)، migrations كخطوة منفصلة، وإضافة خدمة worker (`run_outbox_worker`) إلى `render.yaml`/compose.
4. **P2 بالكامل:** `LLMGateway` موحد يسجل كل استدعاء في `TokenUsage` (الاستدعاءات غير المحسوبة: `services/ai_service.py` حوالي 214 و366 و403، `services/smart_agent_service.py` حوالي 163 و215)، `AgentRuntime.handle`، حدود iterations/deadline، Tool Registry مع فحص المستأجر داخل كل أداة (`services/agent_tools.py`)، فصل محتوى المستخدم عن التعليمات (`EmbedChatAPI` يقبل `history` من العميل).
5. **P3:**
   - DOM-01: حجز ذري (`transaction.atomic` + قفل + قيد DB) في `book_property_viewing` و`book_viewing_from_chat` و`AIAgentCalendarAPI.post` و`ViewingAppointmentCreateSerializer`.
   - DOM-02 / F-29: تكرار العملاء — `Lead.phone` مشفّر ولا تطابق الاستعلامات عليه أبداً (مُثبت). أضف `phone_hash` (HMAC) + backfill + استخدمه في كل مواضع البحث المذكورة في التدقيق، ثم قيد فريد `(agent, phone_hash)` بعد تقرير بالمكرر.
   - DOM-03: Entitlements وحصص صريحة للباقات.
6. **P4:** سجلات JSON منظمة + فلتر إخفاء PII + `request_id`؛ OpenAPI للـ Partner API؛ تثبيت الاعتماديات وفصل أدوات التطوير عن `requirements.txt`؛ فحص dependencies/image في CI.
7. **بنود صغيرة متبقية من التدقيق:**
   - F-18: `increment_conversation` عام بلا حد طلبات.
   - F-19: `test/add-property/` ما زال مربوطاً في `apps/core/urls.py` (حوالي السطر 71).
   - F-21: `GlobalSettings.openai_api_key` يُخزن نصاً.
   - F-23: `set_webhook` معرّف مرتين في `services/whatsapp_service.py`، و`update_status` مكرر في `LeadViewSet`.
   - F-28: قيم افتراضية في `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`.
   - خلل مكتشف: `templates/dashboard/whatsapp_live.html` يرث `dashboard/base.html` غير الموجود (الصفحة ستفشل).
   - `print`/PII ما زالت في بعض ملفات `services/`.
8. **P5:** وثائق `README`, `ARCHITECTURE`, `DEPLOYMENT`, `RUNBOOK`, `API`, `SECURITY`, `BACKUP_RESTORE`, `TROUBLESHOOTING` + تحديث حالة `docs/implementation/traceability-matrix.md` (أعمدة Status فيه لا تعكس كل ما أُنجز بعد).

### 8.4 طريقة التشغيل والتحقق

```powershell
.\venv\Scripts\activate
python scripts\create_dev_env.py        # مرة واحدة: ينشئ .env محلياً
python manage.py migrate
python manage.py runserver
python manage.py run_outbox_worker      # عامل الخلفية (نافذة منفصلة)
python manage.py test tests test_whatsapp_fixes   # لا تشغّل manage.py test بدون labels
python manage.py check; python manage.py makemigrations --check --dry-run
```

> تحذير: ملفات `test_booking.py` و`test_booking_tool.py` و`test_restrictions.py` في جذر المشروع سكربتات يدوية تتصل بخادم حي — لا تُشغَّل ضمن الاختبارات.
> قبل كل commit: فحص Gitleaks (`docker run --rm -v "${PWD}:/repo" -w /repo zricethezav/gitleaks:v8.18.4 protect --staged --source=/repo --redact`).

### 8.5 إجراءات مطلوبة من المالك (لا ينفذها الوكيل)

1. تدوير كل قيمة كانت في `.env.production` (`DJANGO_SECRET_KEY`, `ADMIN_*`, `DB_PASSWORD`, `RESEND_API_KEY`) — و`FIELD_ENCRYPTION_KEY` بتدوير تدريجي فقط (ADR-0003).
2. قرار تنظيف تاريخ Git (force push) أو الاكتفاء بالتدوير.
3. قبل أي نشر: ضبط `STREAMPAY_WEBHOOK_SECRET` و`STREAMPAY_API_KEY`/`STREAMPAY_API_SECRET` (بدونها تُرفض إشعارات الدفع عمداً)، وتشغيل عامل `run_outbox_worker` كخدمة مستقلة، وضبط `REDIS_URL`.
4. بعد النشر: `python manage.py secure_whatsapp_webhooks` ثم `WHATSAPP_WEBHOOK_LEGACY_ALLOWED=False`.
5. إنشاء حساب أدمن Django (`createsuperuser` أو مجموعة `platform_admin`)، واختيارياً `ADMIN_TOTP_SECRET` للتحقق الثنائي.

### 8.6 متغيرات البيئة الجديدة

`PUBLIC_CHAT_TOKEN_MAX_AGE`, `WHATSAPP_WEBHOOK_LEGACY_ALLOWED`, `WHATSAPP_ASYNC_PROCESSING`, `RATE_LIMIT_ENABLED`, `TRUSTED_PROXY_COUNT`, `DATA_UPLOAD_MAX_MEMORY_SIZE`, `OUTBOUND_WEBHOOK_ALLOW_HTTP`, `OUTBOUND_WEBHOOK_TIMEOUT`, `OUTBOX_INLINE_DISPATCH`, `STREAMPAY_WEBHOOK_TOLERANCE_SECONDS`, `ADMIN_LEGACY_KEY_ENABLED`, `ADMIN_TOTP_SECRET`, `ADMIN_SESSION_MAX_AGE` — كلها موثقة بقيم افتراضية آمنة في `config/settings.py`.
