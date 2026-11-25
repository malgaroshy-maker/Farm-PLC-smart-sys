"""Hardware research data (Milestone G, report R), bilingual. One source for the interactive page
and the two docs copies (docs/HARDWARE_RESEARCH.md, docs/HARDWARE_RESEARCH.ar.md).

Prices are USD per unit. `basis` = a key in SOURCES (a public listing found on RESEARCHED_ON) or
"est" (an engineering estimate where no reliable listing was found). 1 USD = 11 LYD (owner).
Presets: minimum (essential only), basic, recommended, premium. An option with no preset is an
alternative the owner can pick in the page's "build your own list".
"""

USD_TO_LYD = 11
RESEARCHED_ON = "2026-11-25"
PRESETS = ("lowest", "minimum", "basic", "recommended", "premium")
PRESET_LABEL = {
    "lowest": {"en": "Lowest cost", "ar": "أقل تكلفة"},
    "minimum": {"en": "Bare minimum", "ar": "الحد الأدنى"},
    "basic": {"en": "Basic", "ar": "أساسي"},
    "recommended": {"en": "Recommended", "ar": "موصى به"},
    "premium": {"en": "Premium", "ar": "متكامل"},
}
PRESET_NOTE = {
    "lowest": {"en": "The bare minimum with a used PLC, a spare laptop as the server, a consumer router, your existing pump starters and your own workers for trenching.",
               "ar": "الحد الأدنى مع PLC مستعمل، وحاسوب محمول احتياطي كخادم، وراوتر منزلي، ومشغّلات المضخات الحالية، وعمالك لأعمال الحفر."},
    "minimum": {"en": "Only what is needed to run the 12 zones automatically and safely from the app.",
                "ar": "فقط ما يلزم لتشغيل المناطق الـ12 تلقائياً وبأمان من التطبيق."},
    "basic": {"en": "Minimum plus soil sensors, cheap fertigation and two cameras.",
              "ar": "الحد الأدنى مع حساسات رطوبة التربة وتسميد بسيط وكاميرتين."},
    "recommended": {"en": "Industrial parts, wireless soil sensors, a pump drive and better protection.",
                    "ar": "قطع صناعية، حساسات تربة لاسلكية، منظّم سرعة للمضخة، وحماية أفضل."},
    "premium": {"en": "Everything, including solar pumping and per-zone pressure.",
                "ar": "كل شيء، بما فيه الضخ بالطاقة الشمسية وضغط كل منطقة."},
}
PHASES = {
    1: {"en": "Phase 1 · automatic irrigation", "ar": "المرحلة 1 · ري تلقائي"},
    2: {"en": "Phase 2 · sensing and savings", "ar": "المرحلة 2 · قياس وتوفير"},
    3: {"en": "Phase 3 · extras", "ar": "المرحلة 3 · إضافات"},
}

# Landed-cost assumptions applied to the hardware subtotal
FREIGHT_AND_PORT = 0.12   # freight/insurance + Libyan 4% port services tax (duties disputed; confirm with a broker)
INSTALL = 0.15            # contractor: local electrician, trenching help, commissioning
INSTALL_OWN = 0.05        # own workers dig and lay cable; an electrician wires the panel only
PRESET_INSTALL = {"lowest": "own"}  # other presets: contractor
CONTINGENCY = 0.10

SOURCES = {
    "s71200g2": ("S7-1200 G2 CPU 1214C retail listings ($600–$860)", "https://www.eandm.com/Products/Content/Siemens/S7-1200G2.aspx"),
    "g2_opcua": ("Siemens forum: S7-1200 G2 OPC UA server from TIA V21", "https://support.industry.siemens.com/forum/ph/en/post/1274978"),
    "et200sp": ("RS Components: ET 200SP CPU 1512SP-1 PN (£927 ex VAT)", "https://uk.rs-online.com/web/p/plcs-programmable-logic-controllers/2032838"),
    "s71511": ("Steiner Electric: S7-1500 CPU 1511-1 PN ($1,590)", "https://www.steinerelectric.com/Product/Siemens-6ES75111AL030AB0-Siemens-S7-1500CPU-1511-1PNMemory-300KB-Prog-1-5MB-Data-1355197"),
    "plc_budget": ("Budget PLC comparison (Delta, Unitronics, S7-1200)", "https://industrialmonitordirect.com/blogs/knowledgebase/budget-plcs-with-remote-io-s7-1200-vs-alternatives"),
    "unistream": ("Unitronics UniStream: OPC UA and Modbus TCP built in", "https://unitronicsplc.com/programmable-controllers-unistream-series/"),
    "mtp1000": ("RS Components UK: MTP1000 Unified Comfort 10.1 in (£2,184 ex VAT)", "https://uk.rs-online.com/web/p/hmi-displays/2823478"),
    "et200sp_io": ("Farnell: ET 200SP DI16 6ES7131-6BH01 (€90 ex VAT), DQ16 6ES7132-6BH01 ($142)", "https://be.farnell.com/en-BE/siemens/6es7131-6bh01-0ba0/digital-input-module-16-input/dp/3994094"),
    "ktp700": ("RS Components: KTP700 Basic (£850 ex VAT)", "https://uk.rs-online.com/web/p/hmi-displays/8643961"),
    "rut241": ("Bechtle: Teltonika RUT241 (€140–€183)", "https://www.bechtle.com/fr-en/shop/teltonika-rut241-industrial-4g-router--4831521--p"),
    "starlink": ("Space in Africa: Starlink's Libya entry on hold (Sep 2026)", "https://spaceinafrica.com/2026/09/13/starlinks-libya-market-entry-remains-on-hold-as-negotiations-continue/"),
    "netafim80": ("HydroBuilder: Netafim Series 80 2\" 24VAC ($156–$196)", "https://hydrobuilder.com/products/netafim-series-80-angle-control-valve-2-inch-24vac-61et2gh2-an"),
    "bermad200": ("NCPW: Bermad 2\" 24VAC 200 series ($335)", "https://ncpw.com/product/bermad-2-24vac-solenoid-controlled-valve-200-series-ir-210-3w-x/"),
    "magmeter_cn": ("Alibaba: DN50 electromagnetic flowmeter 4-20 mA/pulse (~$458)", "https://www.alibaba.com/product-detail/DN50-irrigation-water-flowmeter-industrial-waste_1600086575352.html"),
    "mbs3000": ("TME: Danfoss MBS 3000 0-10 bar 4-20 mA (~$205–$221)", "https://www.tme.eu/gb/details/060G1455/"),
    "level": ("Selection guide: hydrostatic (~$300–$500) vs ultrasonic level", "https://industrialmonitordirect.com/blogs/knowledgebase/water-tank-level-sensors-hydrostatic-vs-ultrasonic-vs-radar-selection"),
    "g120x": ("Bürklin: SINAMICS G120X 7.5 kW (€1,151)", "https://www.buerklin.com/en/p/siemens/variable-speed-drive-and-accessories/6sl3220-3ye24-0up0/80P1912/"),
    "invt_pv": ("INVT GD100-PV solar pump inverter (7.5 kW models)", "https://www.invt.com/products/gd100-pv-series-solar-pump-28"),
    "submonitor": ("Franklin SubMonitor Connect listings ($1,494–$2,831)", "https://rcworst.com/franklin-electric-5860005110-submonitor-connect-premium-1-135a.html"),
    "sdm630": ("Taphome: Eastron SDM630 V3 Modbus meter (€146)", "https://hardware.taphome.com/en/electric-meter/"),
    "dosatron": ("Dosatron D25RE2 price range ($700–$900)", "https://toledoindoorgarden.com/dosing-sliders"),
    "soil_rs485": ("DFRobot RS485 soil moisture/temp/EC sensor ($69–$73)", "https://www.dfrobot.com/product-2830.html"),
    "s2105": ("RobotShop: SenseCAP S2105 LoRaWAN soil sensor ($139)", "https://robotshop.com/products/seeedstudio-sensecap-s2105-lorawan-soil-moisture-temperature-ec-sensor"),
    "ug65": ("AgTech NSW: Milesight UG65 LoRaWAN gateway (~$470)", "https://www.agtech.dpi.nsw.gov.au/collections/connectivity-solutions/products/milesight-lorawan-ug65-semi-industrial-gateway"),
    "uc511": ("MCCI / iot-shop.de: Milesight UC511 LoRaWAN valve controller ($145–$385)", "https://store.mcci.com/products/solenoid-valve-controller-uc51x"),
    "sentek": ("Trellis: Watermark vs Sentek profile probes", "https://www.mytrellis.com/blog/watermark-sentek"),
    "hik_solar": ("Security Wholesalers: Hikvision 4K ColorVu solar 4G kit (AU$3,340)", "https://www.securitywholesalers.com.au/product/hikvision-ds-2xs6a87g1-l-c32s80-4k-colorvu-fixed-bullet-solar-power-4g-network-camera-no-battery/"),
    "libya_customs": ("Bank of Scotland trade guide: Libya customs (4% port tax)", "https://www.bankofscotlandtrade.co.uk/en/market-potential/libya/customs"),
    "libya_procure": ("Libya industrial procurement landscape 2026 (duties 0–25% by HS code)", "https://papaverai.com/blog/libya-industrial-economic-development/"),
    "opcua_lic": ("SIMATIC OPC UA S7-1200 Basic runtime license, 6ES7823-0BA00-2BA0 (€79–€94)", "https://industry-electronics.com/siemens/6es78230ba002ba0-6es7823-0ba00-2ba0-simatic-opc-ua-s7-1200-basic-lieske_1909651.htm"),
    "opcua_lic15": ("SIMATIC OPC UA S7-1500 runtime license datasheet (6ES7823-0BE00-2BA0)", "https://media.distributordatasolutions.com/siemenscomplete/2023q2/documents/e39d93817073cde12a49b42bd04c0248f9fe1d02.pdf"),
    "minipc": ("Shuttle NE10N fanless Intel N100 mini PC (€160–€194)", "https://aio.lv/en/product--shuttle-ne10n--11445919.md"),
    "used1200": ("eBay: used/refurbished S7-1200 CPU 1214C (€256–€520; 90-day used trend ≈ $150)", "https://www.ebay.de/itm/285738109230"),
    "smart200": ("eBay: S7-200 SMART CPU SR20 ($99–$179)", "https://www.ebay.com/itm/315851701171"),
    "b311": ("aio.lv: Huawei B311 4G router (€63–€74)", "https://aio.lv/en/product--huawei-51060dye--6024731.md"),
    "rpi5": ("Raspberry Pi 5 8 GB kits now €240–€255 (memory price rises)", "https://raspberry.tips/en/?p=11327"),
    "ebyte": ("Ebyte E95-DTU RS-485 LoRa radio ($13–$25)", "https://ebyteiot.com/products/ebyte-rs485-lora-radio-station-rf-modbus-3000m-long-distance-wireless-transceiver-20dbm-433m-lora"),
    "motor_valve": ("Ussolid 2\" UPVC motorized ball valve 24 V ($145–$180)", "https://ussolid.com/sv/products/2-double-union-upvc-motorized-ball-valve-dc-24v-6-wire-with-signal-feedback-3w2c-normally-closed-with-manual-override-epdm-seal"),
    "hunter_2wire": ("Hunter two-wire / decoder comparison", "https://hunterirrigation.com/node/486591"),
}

GROUPS = {
    "control": {"en": "Control panel", "ar": "لوحة التحكم"},
    "pumps": {"en": "Pumps and power", "ar": "المضخات والكهرباء"},
    "head": {"en": "Head unit (tank and booster)", "ar": "وحدة الرأس (الخزان ومضخة التعزيز)"},
    "valves": {"en": "Zone valves and cable", "ar": "صمامات المناطق والكوابل"},
    "soil": {"en": "Soil sensors", "ar": "حساسات التربة"},
    "comms": {"en": "Internet and cameras", "ar": "الإنترنت والكاميرات"},
}

LOCATIONS = {
    "control": {"en": "Control room", "ar": "غرفة التحكم",
                "how_en": "PLC cabinet, 24 VAC transformer, UPS, surge protection, energy meters and pump drive inside; 4G router on the outside wall; LoRaWAN gateway mounted high on the roof or a mast; camera recorder.",
                "how_ar": "داخلها: خزانة الـPLC، محوّل 24 فولت متردد، مزوّد الطاقة الاحتياطي، حماية الصواعق، عدادات الكهرباء ومنظّم سرعة المضخة. على الجدار الخارجي: راوتر 4G. على السطح أو سارية: بوابة LoRaWAN. وجهاز تسجيل الكاميرات."},
    "well": {"en": "Wellhead (just north of the control room)", "ar": "رأس البئر (شمال غرفة التحكم مباشرة)",
             "how_en": "Level probe hung in the well about 2 m above the pump intake, on its own cable. The pump protection relay sits in the control room.",
             "how_ar": "حساس المستوى معلّق داخل البئر على ارتفاع نحو 2 م فوق فتحة سحب المضخة، بكابل مستقل. مرحّل حماية المضخة داخل غرفة التحكم."},
    "tank": {"en": "Tank", "ar": "الخزان",
             "how_en": "Hydrostatic level probe at the tank bottom, away from the inlet; cable out through the roof hatch.",
             "how_ar": "حساس المستوى الهيدروستاتيكي في قاع الخزان بعيداً عن مدخل الماء، والكابل يخرج من فتحة السقف."},
    "head": {"en": "Head unit at the booster pad", "ar": "وحدة الرأس عند مضخة التعزيز",
             "how_en": "In this order: tank outlet → booster pump (with drive) → check valve → fertigation injection → filter (clogging switch across it) → flow meter (straight pipe 5× diameter before, 3× after) → pressure transmitter → mainline.",
             "how_ar": "بهذا الترتيب: مخرج الخزان ← مضخة التعزيز (مع منظّم السرعة) ← صمام عدم رجوع ← نقطة حقن السماد ← الفلتر (مع مفتاح الانسداد عبره) ← عداد التدفق (أنبوب مستقيم بطول 5 أضعاف القطر قبله و3 بعده) ← حساس الضغط ← الخط الرئيسي."},
    "field": {"en": "At each zone valve", "ar": "عند صمام كل منطقة",
              "how_en": "Valve in a valve box at the zone's take-off from the trunk; solenoid wires joined with waterproof gel connectors; cable in conduit back along the trunk trench.",
              "how_ar": "الصمام داخل صندوق صمام عند تفرّع المنطقة من الخط الرئيسي، أسلاك الملف موصولة بوصلات جل مقاومة للماء، والكابل داخل أنبوب حماية في خندق الخط الرئيسي."},
    "zones": {"en": "Soil sensor station in each zone", "ar": "محطة حساس الرطوبة في كل منطقة",
              "how_en": "Under a representative tree in the middle of the zone, away from the first and last rows, the valve end and the far end of the drip line; 20–30 cm from a dripper, inside the wet bulb. Mark the tree.",
              "how_ar": "تحت شجرة تمثّل المنطقة في وسطها، بعيداً عن الصفوف الأولى والأخيرة وعن جهة الصمام ونهاية خط التنقيط؛ على بعد 20–30 سم من النقّاطة داخل منطقة البلل. علّم الشجرة."},
    "farm": {"en": "Around the farm", "ar": "حول المزرعة",
             "how_en": "Cameras on the control room, the head unit, the wellhead and the main track; solar panels on a ground frame near the control room.",
             "how_ar": "كاميرات على غرفة التحكم ووحدة الرأس ورأس البئر والطريق الرئيسي؛ الألواح الشمسية على هيكل أرضي قرب غرفة التحكم."},
}


def opt(key, presets, en, ar, qty, unit, basis, note_en="", note_ar=""):
    return {"key": key, "presets": list(presets), "product": {"en": en, "ar": ar}, "qty": qty, "unit": unit,
            "basis": basis, "note": {"en": note_en, "ar": note_ar}}


def item(iid, group, loc, phase, minimum, what_en, what_ar, skip_en, skip_ar, options, local=False):
    return {"id": iid, "group": group, "loc": loc, "phase": phase, "minimum": minimum, "local": local,
            "what": {"en": what_en, "ar": what_ar}, "skip": {"en": skip_en, "ar": skip_ar}, "options": options}


NEEDS_MODBUS = ("Needs a Modbus TCP adapter in the app (a few days of software work, not built yet). Not simulated by your PLCSIM Advanced.",
                "يحتاج محوّل Modbus TCP في التطبيق (عمل برمجي لبضعة أيام، غير منجز بعد). لا يحاكيه PLCSIM Advanced لديك.")

ITEMS = [
    # ── Control panel ───────────────────────────────────────────────────
    item("cpu", "control", "control", 1, True,
         "PLC controller: runs zones and pumps and enforces every safety interlock",
         "وحدة التحكم PLC: تشغّل المناطق والمضخات وتطبّق كل حمايات السلامة",
         "", "", [
             opt("s71200", ("minimum", "basic"), "S7-1200 CPU 1214C DC/DC/RLY (classic)", "S7-1200 CPU 1214C (الجيل الحالي)", 1, 650, "s71200g2",
                 "10 relay outputs built in. OPC UA works in your TIA V19. Being phased out from 1 Nov 2026: buy while stock lasts.",
                 "فيه 10 مخارج ريليه. يعمل OPC UA في TIA V19 لديك. يتوقف إنتاجه من 1 نوفمبر 2026، فاشترِه ما دام متوفراً."),
             opt("used1200", ("lowest",), "Used S7-1200 CPU 1214C (seller warranty)", "S7-1200 CPU 1214C مستعمل (بضمان البائع)", 1, 250, "used1200",
                 "Same as new for the app, TIA V19 and G5. Check firmware 4.4 or newer (needed for OPC UA) and get at least a 1-year warranty.",
                 "مثل الجديد تماماً للتطبيق وTIA V19 وG5. تأكد أن البرنامج الثابت 4.4 أو أحدث (لازم لـOPC UA) واطلب ضماناً سنة على الأقل."),
             opt("smart200", (), "Siemens S7-200 SMART SR30 + EM DR08", "Siemens S7-200 SMART SR30 + وحدة EM DR08", 1, 230, "smart200",
                 "Cheapest Siemens, no OPC UA license needed. Needs a Modbus TCP adapter in the app first; programmed in the free STEP 7-MicroWIN SMART, not TIA.",
                 "أرخص Siemens ولا يحتاج ترخيص OPC UA. يحتاج أولاً محوّل Modbus TCP في التطبيق؛ يُبرمج ببرنامج STEP 7-MicroWIN SMART المجاني وليس TIA."),
             opt("et200sp", ("recommended",), "ET 200SP CPU 1512SP-1 PN (S7-1500 family)", "ET 200SP CPU 1512SP-1 PN (عائلة S7-1500)", 1, 1100, "et200sp",
                 "OPC UA in TIA V19 and simulated by your PLCSIM Advanced, so the G5 tests carry over.",
                 "OPC UA في TIA V19 ويحاكيه PLCSIM Advanced لديك، فتنتقل اختبارات G5 كما هي."),
             opt("s71511", ("premium",), "S7-1500 CPU 1511-1 PN", "S7-1500 CPU 1511-1 PN", 1, 1600, "s71511",
                 "Largest and most expandable; built-in display.", "الأكبر والأكثر قابلية للتوسعة، مع شاشة مدمجة."),
             opt("g2", (), "S7-1200 G2 CPU 1214C", "S7-1200 G2 CPU 1214C (الجيل الجديد)", 1, 700, "g2_opcua",
                 "New generation, but its OPC UA server needs TIA Portal V21 (budget the upgrade).",
                 "الجيل الجديد، لكن خادم OPC UA فيه يحتاج TIA Portal V21 (احسب تكلفة الترقية)."),
             opt("logo", (), "Siemens LOGO! 8.4 + 2 relay expansions", "Siemens LOGO! 8.4 مع وحدتي توسعة ريليه", 1, 450, "est", *NEEDS_MODBUS),
             opt("delta", (), "Delta AS228R + relay and analog modules", "Delta AS228R مع وحدات ريليه وتناظري", 1, 450, "plc_budget", *NEEDS_MODBUS),
             opt("unistream", (), "Unitronics UniStream with built-in touch screen", "Unitronics UniStream مع شاشة لمس مدمجة", 1, 900, "unistream",
                 "Has OPC UA, so the app's adapter works; programmed in its own free software, not TIA.",
                 "يدعم OPC UA فيعمل مع محوّل التطبيق الحالي؛ يُبرمج ببرنامجه المجاني وليس TIA."),
         ]),
    item("io", "control", "control", 1, True,
         "Extra outputs and inputs (12 valves + 2 pumps need 14 outputs)",
         "مخارج ومداخل إضافية (12 صماماً ومضختان تحتاج 14 مخرجاً)",
         "", "", [
             opt("used", ("lowest",), "Used SM 1222 DQ8 relay", "SM 1222 مستعمل بثماني مخارج ريليه", 1, 70, "est"),
             opt("min", ("minimum",), "SM 1222 DQ8 relay (4-20 mA read on the CPU's inputs)", "SM 1222 ثماني مخارج ريليه (قراءة 4-20 مللي أمبير على مداخل الوحدة)", 1, 180, "est"),
             opt("basic", ("basic",), "SM 1222 DQ16 relay + SM 1231 AI4", "SM 1222 ست عشرة مخرج ريليه + SM 1231 أربع مداخل تناظرية", 1, 450, "est"),
             opt("rec", ("recommended",), "ET 200SP as built: 3× DI16 (panel switches, zone ON/OFF), DQ16 + DQ8 (24 V DC valves and pumps), AI8 (tank, pressure, flow, well, filter), server module, base units",
                 "ET 200SP كما بُني: 3× مداخل رقمية 16 (مفاتيح اللوحة)، مخارج 16 + 8 (صمامات ومضخات 24 فولت)، مداخل تناظرية 8 (الخزان والضغط والتدفق والبئر والفلتر)، وحدة الخادم، قواعد التركيب",
                 1, 1250, "et200sp_io",
                 "The design in TIA (G5) uses 3× 6ES7131-6BH01, 6ES7132-6BH01, 6ES7132-6BF01, 6ES7134-6GF00 and a server module. The outputs are 24 V DC transistor outputs, so each valve and pump starter needs an interposing relay (in the cabinet item).",
                 "التصميم في TIA (G5) يستخدم 3× 6ES7131-6BH01 و6ES7132-6BH01 و6ES7132-6BF01 و6ES7134-6GF00 ووحدة خادم. المخارج ترانزستورية 24 فولت، لذا يحتاج كل صمام ومشغّل مضخة إلى ريليه وسيط (ضمن بند الخزانة)."),
             opt("prem", ("premium",), "S7-1500: DI32, DQ32 relay, AI8", "S7-1500: مداخل 32، مخارج ريليه 32، تناظري 8", 1, 1800, "est"),
         ]),
    item("opcua", "control", "control", 1, True,
         "OPC UA runtime license (lets the app talk to the PLC)", "ترخيص تشغيل OPC UA (يسمح للتطبيق بالتواصل مع الـPLC)",
         "", "", [
             opt("s71200", ("lowest", "minimum", "basic"), "SIMATIC OPC UA S7-1200 Basic", "SIMATIC OPC UA S7-1200 Basic", 1, 100, "opcua_lic",
                 "One per S7-1200 CPU.", "ترخيص واحد لكل وحدة S7-1200."),
             opt("s71500", ("recommended", "premium"), "SIMATIC OPC UA S7-1500 Small", "SIMATIC OPC UA S7-1500 Small", 1, 250, "opcua_lic15",
                 "One per S7-1500-family CPU (including ET 200SP).", "ترخيص واحد لكل وحدة من عائلة S7-1500 (ومنها ET 200SP)."),
         ]),
    item("server", "control", "control", 1, True,
         "Farm server: an always-on computer that runs the app and its database", "خادم المزرعة: حاسوب يعمل دائماً ويشغّل التطبيق وقاعدة بياناته",
         "", "", [
             opt("laptop", ("lowest",), "A spare laptop you already have (its battery covers short power cuts)", "حاسوب محمول احتياطي لديك (بطاريته تغطي انقطاعات الكهرباء القصيرة)", 1, 0, "est",
                 "Any laptop from the last 8 years with 8 GB RAM. Keep it plugged in, lid closed, in the cabinet room.",
                 "أي حاسوب محمول من آخر 8 سنوات بذاكرة 8 GB. يبقى موصولاً بالكهرباء والغطاء مغلق في غرفة التحكم."),
             opt("rpi", (), "Raspberry Pi 5 8 GB kit with SSD", "طقم Raspberry Pi 5 بذاكرة 8 GB مع SSD", 1, 270, "rpi5",
                 "No longer cheaper: memory price rises put Pi 5 kits above an N100 mini PC in 2026.",
                 "لم يعد أرخص: ارتفاع أسعار الذاكرة جعل أطقم Pi 5 أغلى من حاسوب N100 الصغير في 2026."),
             opt("min", ("minimum", "basic"), "Fanless mini PC (Intel N100, 16 GB, 512 GB SSD) + 5-port switch", "حاسوب صغير بلا مروحة (Intel N100، 16 GB، SSD 512 GB) + مبدّل شبكة 5 منافذ", 1, 230, "minipc"),
             opt("rec", ("recommended",), "Industrial fanless N100 PC, 12–24 V DC input + switch", "حاسوب صناعي بلا مروحة N100 بتغذية 12–24 فولت مستمر + مبدّل", 1, 380, "est"),
             opt("prem", ("premium",), "Industrial PC with two mirrored SSDs + managed switch", "حاسوب صناعي بقرصي SSD متطابقين + مبدّل مُدار", 1, 850, "est"),
         ]),
    item("estop", "control", "control", 1, True,
         "Emergency stop button, Auto/Off/Manual switch and indicator lights on the panel", "زر إيقاف طوارئ، مفتاح تلقائي/إيقاف/يدوي ومصابيح بيان على اللوحة",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "E-stop, 3-position switch, 3 pilot lights", "زر طوارئ، مفتاح 3 أوضاع، 3 مصابيح", 1, 90, "est"),
             opt("rec", ("recommended", "premium"), "E-stop with safety relay, switch, lights, buzzer", "زر طوارئ مع مرحّل أمان، مفتاح، مصابيح، جرس", 1, 220, "est"),
         ]),
    item("override", "control", "control", 1, True,
         "Manual override on the panel: On/Auto/Off switch per zone and Hand/Off/Auto per pump, plus a pressure gauge",
         "تشغيل يدوي من اللوحة: مفتاح تشغيل/تلقائي/إيقاف لكل منطقة ويدوي/إيقاف/تلقائي لكل مضخة، مع مقياس ضغط",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "14 selector switches, labels, analog pressure gauge", "14 مفتاح اختيار، ملصقات، مقياس ضغط عادي", 1, 180, "est",
                 "Hand mode powers the valve or pump directly, so irrigation goes on if the PLC or the app is down. The pump protection relay stays wired in.",
                 "الوضع اليدوي يغذي الصمام أو المضخة مباشرة، فيستمر الري إذا توقف الـPLC أو التطبيق. يبقى مرحّل حماية المضخة موصولاً."),
             opt("rec", ("recommended", "premium"), "14 industrial 22 mm selectors with lamps + gauge", "14 مفتاحاً صناعياً 22 مم بمصابيح + مقياس ضغط", 1, 320, "est"),
         ]),
    item("rs485", "control", "control", 2, False,
         "RS-485/Modbus port for energy meters and wired sensors", "منفذ RS-485/Modbus لعدادات الكهرباء والحساسات السلكية",
         "Needed only for wired soil sensors or energy meters.", "يلزم فقط للحساسات السلكية أو عدادات الكهرباء.", [
             opt("used", (), "Used CM 1241 RS-485", "CM 1241 RS-485 مستعمل", 1, 60, "est"),
             opt("basic", ("basic",), "CM 1241 RS-485", "CM 1241 RS-485", 1, 150, "est"),
             opt("rec", ("recommended", "premium"), "ET 200SP CM PtP", "ET 200SP CM PtP", 1, 350, "est"),
         ]),
    item("mc", "control", "control", 1, False,
         "Memory card (required by S7-1500 family CPUs)", "بطاقة ذاكرة (إلزامية لوحدات عائلة S7-1500)",
         "Not needed with the S7-1200.", "لا تلزم مع S7-1200.", [
             opt("mc", ("recommended", "premium"), "SIMATIC Memory Card 4 MB", "بطاقة SIMATIC سعة 4 ميغابايت", 1, 80, "est"),
         ]),
    item("hmi", "control", "control", 3, False,
         "Touch screen on the panel", "شاشة لمس على اللوحة",
         "The app already works on any phone or computer.", "التطبيق يعمل أصلاً على أي هاتف أو حاسوب.", [
             opt("mtp1000", ("recommended", "premium"), "MTP1000 Unified Comfort 10\" (as designed in G5, Arabic and English)", "MTP1000 Unified Comfort مقاس 10 بوصة (كما صُمّم في G5، عربي وإنجليزي)", 1, 2600, "mtp1000",
                 "The HMI is built and tested in the simulator: six screens in Arabic. Needs a WinCC Unified licence (engineering is included in your TIA).",
                 "الشاشة مبنية ومجرّبة في المحاكي: ست شاشات بالعربية. تحتاج ترخيص WinCC Unified (الهندسة متضمنة في TIA لديك)."),
             opt("ktp700", (), "KTP700 Basic 7\" (cheaper, not Unified: the screens would need rebuilding)", "KTP700 Basic مقاس 7 بوصة (أرخص وليست Unified: تلزم إعادة بناء الشاشات)", 1, 1050, "ktp700"),
         ]),
    item("cabinet", "control", "control", 1, True,
         "Cabinet with DIN rails, breakers, terminals and wiring", "خزانة كهربائية مع قضبان التثبيت والقواطع والأطراف والتمديدات",
         "", "", [
             opt("local", ("lowest",), "Locally made 600×600 steel cabinet, sealed", "خزانة حديد محلية الصنع 600×600 محكمة", 1, 250, "est"),
             opt("min", ("minimum", "basic"), "600×600 IP65 cabinet", "خزانة 600×600 بحماية IP65", 1, 450, "est"),
             opt("rec", ("recommended",), "800×600 IP65 with cooling fan", "خزانة 800×600 بحماية IP65 مع مروحة تبريد", 1, 800, "est"),
             opt("prem", ("premium",), "800×800 IP66 with fan, heater, door switch", "خزانة 800×800 بحماية IP66 مع مروحة وسخان ومفتاح باب", 1, 1300, "est"),
         ]),
    item("trafo", "control", "control", 1, True,
         "24 VAC transformer for the valve coils", "محوّل 24 فولت متردد لملفات الصمامات",
         "", "", [
             opt("t", ("lowest", "minimum", "basic", "recommended", "premium"), "150 VA 230/24 VAC with fuses", "محوّل 150 فولت أمبير 230/24 مع منصهرات", 1, 80, "est"),
         ]),
    item("relays", "control", "control", 2, False,
         "Interface relays between PLC and valves", "مرحّلات وسيطة بين الـPLC والصمامات",
         "The S7-1200 relay outputs can drive the coils directly; relays make swaps cheaper.",
         "مخارج الريليه في S7-1200 تشغّل الملفات مباشرة؛ المرحّلات تجعل الاستبدال أرخص.", [
             opt("basic", ("basic",), "14 plug-in relays", "14 مرحّلاً قابلاً للنزع", 14, 8, "est"),
             opt("rec", ("recommended",), "14 industrial relays with LED", "14 مرحّلاً صناعياً بمؤشر", 14, 15, "est"),
             opt("prem", ("premium",), "14 relays with manual override", "14 مرحّلاً مع تشغيل يدوي", 14, 20, "est"),
         ]),
    item("psu", "control", "control", 1, True,
         "24 VDC power supply for PLC and sensors", "مزوّد طاقة 24 فولت مستمر للـPLC والحساسات",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "DIN-rail 24 V 5 A", "24 فولت 5 أمبير على قضيب", 1, 60, "est"),
             opt("rec", ("recommended",), "SITOP 24 V 5 A", "SITOP 24 فولت 5 أمبير", 1, 150, "est"),
             opt("prem", ("premium",), "SITOP 24 V 10 A", "SITOP 24 فولت 10 أمبير", 1, 200, "est"),
         ]),
    item("ups", "control", "control", 2, False,
         "Backup power for PLC, router and farm server", "طاقة احتياطية للـPLC والراوتر وخادم المزرعة",
         "Your grid is stable; without it a power cut restarts the PLC and the server, and the app is offline until power returns.",
         "الكهرباء عندك مستقرة؛ بدونه يعيد انقطاع الكهرباء تشغيل الـPLC والخادم ويتوقف التطبيق حتى عودة الكهرباء.", [
             opt("rec", ("recommended",), "24 V DC UPS + 7 Ah battery", "UPS بجهد 24 فولت مع بطارية 7 أمبير ساعة", 1, 300, "est"),
             opt("prem", ("premium",), "24 V DC UPS + 12 Ah battery with monitoring", "UPS بجهد 24 فولت مع بطارية 12 أمبير ساعة ومراقبة", 1, 600, "est"),
         ]),
    item("spd", "control", "control", 1, True,
         "Surge and lightning protection", "حماية من الصواعق وارتفاع الجهد",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "Mains surge protector", "واقي جهد على التغذية الرئيسية", 1, 120, "est"),
             opt("rec", ("recommended",), "Mains + field-cable surge protectors", "واقيات على التغذية وعلى كوابل الحقل", 1, 350, "est"),
             opt("prem", ("premium",), "Type 1+2 mains + field-cable protectors", "واقيات نوع 1+2 مع واقيات كوابل الحقل", 1, 600, "est"),
         ]),
    # ── Pumps and power ─────────────────────────────────────────────────
    item("pumpprot", "pumps", "control", 1, True,
         "Well pump protection: dry run, overload, phase loss", "حماية مضخة البئر: التشغيل على الجاف، الحمل الزائد، فقدان الطور",
         "", "", [
             opt("min", ("lowest", "minimum", "basic", "recommended"), "Phase and underload protection relay", "مرحّل حماية الطور والحمل المنخفض", 1, 90, "est"),
             opt("prem", ("premium",), "Franklin SubMonitor Connect", "Franklin SubMonitor Connect", 1, 2000, "submonitor"),
         ]),
    item("starters", "pumps", "control", 1, True,
         "Motor starters the PLC switches (contactor, overload relay, run feedback)", "مشغّلات المضخات التي يتحكم بها الـPLC (كونتاكتور، مرحّل حمل زائد، إشارة تشغيل)",
         "", "", [
             opt("reuse", ("lowest",), "Reuse the existing starters", "استخدام المشغّلات الحالية", 1, 0, "est",
                 "Works if each has a 24 V AC/DC coil (or add a $15 interface relay) and a free auxiliary contact for run feedback. Check on site.",
                 "يصلح إذا كان لكل منها ملف 24 فولت (أو أضف مرحّلاً وسيطاً بنحو 15$) ونقطة مساعدة حرة لإشارة التشغيل. تحقق في الموقع."),
             opt("two", ("minimum", "basic"), "2 starters: well pump and booster", "مشغّلان: مضخة البئر ومضخة التعزيز", 2, 150, "est",
                 "Reuse existing starters if they have a 24 V coil and an auxiliary contact.", "يمكن استخدام المشغّلات الحالية إذا كان ملفها 24 فولت وفيها نقطة مساعدة."),
             opt("one", ("recommended",), "1 starter for the well pump (the booster runs on its drive)", "مشغّل واحد لمضخة البئر (مضخة التعزيز تعمل بمنظّم السرعة)", 1, 150, "est"),
         ]),
    item("meter", "pumps", "control", 2, False,
         "Energy meter per pump", "عداد كهرباء لكل مضخة",
         "Without it you can't see a pump's energy use rising before it fails.", "بدونه لا ترى ارتفاع استهلاك المضخة قبل أن تتعطل.", [
             opt("m", ("recommended", "premium"), "Eastron SDM630 Modbus", "Eastron SDM630 بـ Modbus", 2, 150, "sdm630"),
         ]),
    item("vfd", "pumps", "control", 2, False,
         "Pump speed drive: steady pressure, soft start, less energy", "منظّم سرعة المضخة: ضغط ثابت، بدء ناعم، طاقة أقل",
         "The booster runs at full speed with a direct starter, as today.", "تعمل مضخة التعزيز بالسرعة الكاملة بمشغّل مباشر كما هي اليوم.", [
             opt("rec", ("recommended",), "SINAMICS G120X 7.5 kW on the booster", "SINAMICS G120X بقدرة 7.5 ك.و على مضخة التعزيز", 1, 1300, "g120x"),
             opt("prem", ("premium",), "SINAMICS G120X 7.5 kW on the booster (the solar inverter drives the well pump)", "SINAMICS G120X على مضخة التعزيز (العاكس الشمسي يشغّل مضخة البئر)", 1, 1300, "g120x"),
             opt("both", (), "SINAMICS G120X on booster and well pump (no solar)", "SINAMICS G120X على المضختين (بدون طاقة شمسية)", 2, 1300, "g120x"),
         ]),
    item("solar", "pumps", "farm", 3, False,
         "Solar pumping for the well pump (inverter, ~11 kWp panels, frame and cables)",
         "ضخ بالطاقة الشمسية لمضخة البئر (عاكس، ألواح نحو 11 ك.و ذروة، هيكل وكوابل)",
         "Grid stays the only source. Solar mainly adds resilience; check your tariff before counting on savings.",
         "تبقى الشبكة المصدر الوحيد. الطاقة الشمسية تضيف استقلالية أساساً؛ راجع تعرفة الكهرباء قبل حساب التوفير.", [
             opt("prem", ("premium",), "INVT GD100-PV 7.5 kW + ≈20 × 550 W panels + mounting", "INVT GD100-PV بقدرة 7.5 ك.و + نحو 20 لوحاً بقدرة 550 واط + التركيب", 1, 5700, "invt_pv"),
         ]),
    # ── Head unit ───────────────────────────────────────────────────────
    item("flow", "head", "head", 1, True,
         "Main flow meter: water per zone, leak and blocked-dripper alarms", "عداد التدفق الرئيسي: مياه كل منطقة وإنذارات التسريب وانسداد النقّاطات",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "2\" Woltman meter with pulse output", "عداد Woltman مقاس 2 بوصة بمخرج نبضات", 1, 180, "est"),
             opt("rec", ("recommended",), "DN50 electromagnetic meter, 4-20 mA + pulse", "عداد كهرومغناطيسي DN50 بمخرج 4-20 مللي أمبير ونبضات", 1, 460, "magmeter_cn"),
             opt("prem", ("premium",), "Siemens SITRANS FM MAG 5100 W DN50", "Siemens SITRANS FM MAG 5100 W مقاس DN50", 1, 2500, "est"),
         ]),
    item("pressure", "head", "head", 1, True,
         "Main pressure transmitter", "حساس الضغط الرئيسي",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "Generic 0-10 bar 4-20 mA", "حساس عام 0-10 بار 4-20 مللي أمبير", 1, 40, "est"),
             opt("rec", ("recommended",), "Danfoss MBS 3000 0-10 bar", "Danfoss MBS 3000 مدى 0-10 بار", 1, 210, "mbs3000"),
             opt("prem", ("premium",), "Danfoss MBS 3000, before and after the filter", "Danfoss MBS 3000 قبل الفلتر وبعده", 2, 210, "mbs3000"),
         ]),
    item("dp", "head", "head", 2, False,
         "Filter clogging alarm", "إنذار انسداد الفلتر",
         "You check the filter by hand on a schedule.", "تفحص الفلتر يدوياً بشكل دوري.", [
             opt("rec", ("recommended",), "Differential pressure switch", "مفتاح فرق الضغط", 1, 90, "est"),
             opt("prem", ("premium",), "From the two pressure transmitters (no extra part)", "من حساسي الضغط قبل الفلتر وبعده (بلا قطعة إضافية)", 1, 0, "est"),
         ]),
    item("tanklevel", "head", "tank", 1, True,
         "Tank level (continuous)", "مستوى الخزان (قياس مستمر)",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "Generic hydrostatic 4-20 mA", "حساس هيدروستاتيكي عام 4-20 مللي أمبير", 1, 80, "est"),
             opt("rec", ("recommended",), "Industrial hydrostatic 4-20 mA", "حساس هيدروستاتيكي صناعي 4-20 مللي أمبير", 1, 320, "level"),
             opt("prem", ("premium",), "Radar level transmitter", "حساس مستوى رادار", 1, 900, "est"),
         ]),
    item("welllevel", "head", "well", 2, False,
         "Water level in the well", "مستوى الماء في البئر",
         "Dry-run protection then relies on the pump relay alone.", "تعتمد حماية التشغيل على الجاف حينها على مرحّل المضخة وحده.", [
             opt("rec", ("recommended", "premium"), "Hydrostatic probe on its own cable", "حساس هيدروستاتيكي بكابل مستقل", 1, 350, "est"),
         ]),
    item("fert", "head", "head", 3, False,
         "Fertigation: fertilizer through the drip lines", "التسميد مع الري عبر خطوط التنقيط",
         "Fertilizer stays manual.", "يبقى التسميد يدوياً.", [
             opt("basic", ("basic",), "Venturi injector + 200 L tank", "حاقن فنتوري + خزان 200 لتر", 1, 150, "est"),
             opt("rec", ("recommended",), "Dosatron D25RE2 + 200 L tank", "Dosatron D25RE2 + خزان 200 لتر", 1, 950, "dosatron"),
             opt("prem", ("premium",), "PLC-controlled dosing pump + EC/pH controller", "مضخة حقن يتحكم بها الـPLC + متحكم EC/pH", 1, 2800, "est"),
         ]),
    # ── Zone valves and cable ───────────────────────────────────────────
    item("v2", "valves", "field", 1, True,
         "2\" zone valves (Zaytoun, Rumman Jadeed, Fruit mix)", "صمامات 2 بوصة (زيتون، رمان جديد، خوخ ومشمش وعوينة)",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "Plastic hydraulic valve + 24 VAC coil", "صمام هيدروليكي بلاستيكي + ملف 24 فولت متردد", 3, 90, "est",
                 "Has a manual bleed screw: open the valve by hand if the system is down.", "فيه برغي تنفيس يدوي: افتح الصمام يدوياً إذا توقف النظام."),
             opt("motor", (), "Motorized ball valve 24 V with position feedback", "صمام كروي بمحرك 24 فولت مع إشارة الوضع", 3, 160, "motor_valve",
                 "More expensive than hydraulic valves; useful only where water pressure is too low for a hydraulic valve.", "أغلى من الصمامات الهيدروليكية؛ مفيد فقط حيث الضغط أقل من أن يشغّل صماماً هيدروليكياً."),
             opt("rec", ("recommended",), "Netafim Series 80, 24 VAC", "Netafim Series 80 بجهد 24 فولت", 3, 195, "netafim80"),
             opt("prem", ("premium",), "Bermad 200 with pressure-regulating pilot", "Bermad 200 مع منظّم ضغط", 3, 340, "bermad200"),
         ]),
    item("v15", "valves", "field", 1, True,
         "1½\" zone valves (Rumman 1–6)", "صمامات 1.5 بوصة (رمان 1 إلى 6)",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "Plastic hydraulic valve + 24 VAC coil", "صمام هيدروليكي بلاستيكي + ملف 24 فولت متردد", 6, 70, "est",
                 "Has a manual bleed screw: open the valve by hand if the system is down.", "فيه برغي تنفيس يدوي: افتح الصمام يدوياً إذا توقف النظام."),
             opt("rec", ("recommended",), "Netafim Series 80, 24 VAC", "Netafim Series 80 بجهد 24 فولت", 6, 150, "est"),
             opt("prem", ("premium",), "Bermad 200 with pressure-regulating pilot", "Bermad 200 مع منظّم ضغط", 6, 280, "est"),
         ]),
    item("v1", "valves", "field", 1, True,
         "1\" zone valves (Rumman Ummahat, Enab, Zaytoun 2)", "صمامات 1 بوصة (رمان أمهات، عنب، زيتون 2)",
         "", "", [
             opt("min", ("lowest", "minimum", "basic"), "Plastic solenoid valve 24 VAC", "صمام كهربائي بلاستيكي 24 فولت", 3, 45, "est",
                 "Turn the solenoid a quarter turn to open it by hand.", "أدِر الملف ربع دورة لفتحه يدوياً."),
             opt("rec", ("recommended",), "Netafim Series 80, 24 VAC", "Netafim Series 80 بجهد 24 فولت", 3, 110, "est"),
             opt("prem", ("premium",), "Bermad 200 with pressure-regulating pilot", "Bermad 200 مع منظّم ضغط", 3, 220, "est"),
         ]),
    item("vbox", "valves", "field", 1, True,
         "Valve box per valve", "صندوق لكل صمام",
         "", "", [
             opt("diy", ("lowest",), "Locally made box (concrete ring or cut drum with lid)", "صندوق محلي (حلقة إسمنت أو برميل مقصوص بغطاء)", 12, 8, "est"),
             opt("min", ("minimum", "basic"), "Plastic valve box", "صندوق صمام بلاستيكي", 12, 20, "est"),
             opt("rec", ("recommended", "premium"), "Heavy-duty box with lid lock", "صندوق متين بقفل للغطاء", 12, 35, "est"),
         ]),
    item("vcable", "valves", "field", 1, True,
         "Valve cable along the three pipe trunks (~800 m)", "كابل الصمامات على امتداد الخطوط الرئيسية الثلاثة (نحو 800 م)",
         "", "", [
             opt("mixed", ("lowest",), "1.0 mm² to the 6 near zones, 1.5 mm² to the far ones (per m)", "1.0 مم² للمناطق الست القريبة و1.5 مم² للبعيدة (للمتر)", 800, 1.2, "est",
                 "Far zones (over 150 m) keep 1.5 mm² so the valve coils get enough voltage.", "المناطق البعيدة (أكثر من 150 م) تبقى 1.5 مم² ليصل جهد كافٍ لملفات الصمامات."),
             opt("near", (), "Cable to the 6 near zones only (~250 m); far zones on wireless boxes", "كابل للمناطق الست القريبة فقط (نحو 250 م)؛ البعيدة على صناديق لاسلكية", 250, 1.2, "est"),
             opt("min", ("minimum", "basic"), "Direct-burial multicore 1.5 mm² (per m)", "كابل متعدد الأسلاك 1.5 مم² للدفن المباشر (للمتر)", 800, 1.5, "est"),
             opt("rec", ("recommended",), "Multicore in conduit (per m)", "كابل متعدد داخل أنبوب حماية (للمتر)", 800, 2.0, "est"),
             opt("prem", ("premium",), "Armoured multicore (per m)", "كابل مدرّع متعدد الأسلاك (للمتر)", 800, 2.5, "est"),
         ]),
    item("trench", "valves", "field", 1, True,
         "Trench work in the existing pipe trenches", "أعمال الحفر في خنادق الأنابيب الحالية",
         "", "", [
             opt("own", ("lowest",), "Your own workers, in the open pipe trenches", "عمالك، في خنادق الأنابيب المفتوحة", 800, 0, "est"),
             opt("min", ("minimum", "basic"), "Local labour (per m)", "عمالة محلية (للمتر)", 800, 1.0, "est"),
             opt("rec", ("recommended",), "Labour + conduit (per m)", "عمالة + أنبوب حماية (للمتر)", 800, 1.5, "est"),
             opt("prem", ("premium",), "Labour + conduit + warning tape (per m)", "عمالة + أنبوب + شريط تحذير (للمتر)", 800, 2.0, "est"),
         ], local=True),
    item("wireless_valves", "valves", "field", 1, False,
         "Wireless instead of cable (whole farm or the far zones only)", "اتصال لاسلكي بدل الكابل (للمزرعة كلها أو المناطق البعيدة فقط)",
         "Not needed when every valve is cabled.", "لا يلزم إذا كانت كل الصمامات موصولة بكابل.", [
             opt("boxes", (), "3 solar radio boxes for the far zones (north, west, south-east) + 6 latching coils", "3 صناديق لاسلكية شمسية للمناطق البعيدة (الشمال، الغرب، الجنوب الشرقي) + 6 ملفات مغناطيسية", 1, 600, "ebyte",
                 "Each box: LoRa radio, Modbus relay board, 20 W panel and battery, valves on DC latching coils. Commands use an on-timer, so a lost radio closes the valve. With your own workers digging, cable costs about the same and is more reliable.",
                 "كل صندوق: راديو LoRa، لوحة مرحّلات Modbus، لوح شمسي 20 واط وبطارية، والصمامات بملفات مغناطيسية. الأوامر بمؤقت تشغيل، فإذا انقطع الراديو يُغلق الصمام. إذا حفر عمالك، يكلّف الكابل تقريباً نفس المبلغ وهو أكثر موثوقية."),
             opt("uc511", (), "LoRaWAN battery controller at every valve (Milesight UC511) + latching coil", "متحكم LoRaWAN بالبطارية عند كل صمام (Milesight UC511) + ملف مغناطيسي", 12, 245, "uc511",
                 "No trenching at all; batteries to change every 1–2 years; needs the LoRaWAN gateway.", "بلا حفر إطلاقاً؛ البطاريات تُستبدل كل سنة أو سنتين؛ يحتاج بوابة LoRaWAN."),
         ]),
    item("zonep", "valves", "field", 3, False,
         "Pressure transmitter after each zone valve (+ signal cable)", "حساس ضغط بعد صمام كل منطقة (+ كابل إشارة)",
         "Leaks and clogs are found per zone from the main meter instead.", "يُكتشف التسريب والانسداد لكل منطقة من العداد الرئيسي بدلاً من ذلك.", [
             opt("prem", ("premium",), "12 × Danfoss MBS 3000 + 800 m signal cable", "12 حساس Danfoss MBS 3000 + كابل إشارة 800 م", 1, 3720, "mbs3000"),
         ]),
    # ── Soil sensors ────────────────────────────────────────────────────
    item("soil", "soil", "zones", 2, False,
         "Soil moisture sensors (21 sensors at 12 stations)", "حساسات رطوبة التربة (21 حساساً في 12 محطة)",
         "Irrigation follows the schedules and the weather advisor only, not the measured soil water.",
         "يتبع الري الجداول ومستشار الطقس فقط، وليس رطوبة التربة المقاسة.", [
             opt("basic", ("basic",), "RS-485 moisture/temperature/EC probes, wired (+ 800 m bus cable)", "حساسات RS-485 سلكية للرطوبة والحرارة والملوحة (+ كابل 800 م)", 1, 2215, "soil_rs485",
                 "Read by the PLC over RS-485; the PLC program and tag map need the sensor tags (part of G5).", "يقرأها الـPLC عبر RS-485؛ يحتاج برنامج الـPLC وخريطة الوسوم إضافتها (ضمن G5)."),
             opt("rec", ("recommended",), "SenseCAP S2105 LoRaWAN probes (battery, no cable)", "حساسات SenseCAP S2105 لاسلكية (بطارية، بلا كابل)", 21, 140, "s2105",
                 "The app needs an MQTT input from the gateway (a few days of software work, not built yet).", "يحتاج التطبيق مدخل MQTT من البوابة (عمل برمجي لبضعة أيام، غير منجز بعد)."),
             opt("prem", ("premium",), "Multi-depth profile probe per zone (every 10 cm to 60 cm)", "مسبار متعدد الأعماق لكل منطقة (كل 10 سم حتى 60 سم)", 12, 900, "est",
                 "Wireless logger; same MQTT input as above.", "مسجّل لاسلكي؛ نفس مدخل MQTT أعلاه."),
         ]),
    item("gateway", "soil", "control", 2, False,
         "LoRaWAN gateway (covers the whole farm)", "بوابة LoRaWAN (تغطي المزرعة كلها)",
         "Only needed for wireless sensors.", "تلزم فقط للحساسات اللاسلكية.", [
             opt("g", ("recommended", "premium"), "Milesight UG65", "Milesight UG65", 1, 470, "ug65"),
         ]),
    # ── Internet and cameras ────────────────────────────────────────────
    item("router", "comms", "control", 1, True,
         "4G router: use the app from anywhere (VPN)", "راوتر 4G: استخدام التطبيق من أي مكان (VPN)",
         "", "", [
             opt("consumer", ("lowest",), "Consumer 4G router (Huawei B311) + free VPN on the farm server", "راوتر 4G منزلي (Huawei B311) + VPN مجاني على خادم المزرعة", 1, 75, "b311",
                 "Remote access through a free VPN (WireGuard/Tailscale) on the server; less rugged than an industrial router.",
                 "الوصول عن بُعد عبر VPN مجاني (WireGuard/Tailscale) على الخادم؛ أقل متانة من الراوتر الصناعي."),
             opt("min", ("minimum", "basic"), "Teltonika RUT241", "Teltonika RUT241", 1, 200, "rut241"),
             opt("rec", ("recommended",), "Teltonika RUT241 + outdoor 4G antenna", "Teltonika RUT241 + هوائي 4G خارجي", 1, 260, "rut241"),
             opt("prem", ("premium",), "Teltonika RUT956 dual-SIM (Libyana + Almadar) + antenna", "Teltonika RUT956 بشريحتين (ليبيانا + المدار) + هوائي", 1, 380, "est"),
         ]),
    item("cams", "comms", "farm", 3, False,
         "Cameras viewable on the phone", "كاميرات تُشاهد من الهاتف",
         "No video of the farm.", "لا فيديو للمزرعة.", [
             opt("basic", ("basic",), "2 PoE cameras + recorder", "كاميرتان PoE + جهاز تسجيل", 1, 450, "est"),
             opt("rec", ("recommended", "premium"), "4 PoE cameras + recorder + PoE switch", "4 كاميرات PoE + جهاز تسجيل + مبدّل PoE", 1, 950, "est"),
         ]),
    item("cam4g", "comms", "farm", 3, False,
         "Solar 4G camera for the far south end", "كاميرا شمسية 4G للطرف الجنوبي البعيد",
         "The south end has no camera.", "لا كاميرا في الطرف الجنوبي.", [
             opt("prem", ("premium",), "Hikvision ColorVu solar 4G kit", "طقم Hikvision ColorVu شمسي 4G", 1, 2200, "hik_solar"),
         ]),
]

CROP_DEPTHS = {"olives": (30, 60), "pomegranate": (30, 60), "mixed_fruit": (30, 60), "grapes": (20, 50)}
SMALL_ZONE_HA = 0.5
CROP_LABEL = {
    "olives": {"en": "Olives", "ar": "زيتون"}, "pomegranate": {"en": "Pomegranate", "ar": "رمان"},
    "mixed_fruit": {"en": "Stone fruit", "ar": "فواكه ذات نواة"}, "grapes": {"en": "Grapes", "ar": "عنب"},
}

T = {  # page text
    "title": {"en": "Hardware plan for the smart irrigation system", "ar": "خطة المعدات لنظام الري الذكي"},
    "lede": {"en": "What to buy, where each piece goes and what it costs for 12 drip zones on about 9 ha. Pick a starting point, then tick or untick items and change any option; the totals update.",
             "ar": "ما يجب شراؤه، وأين يُركّب كل جزء، وكم يكلّف، لـ12 منطقة ري بالتنقيط على نحو 9 هكتارات. اختر نقطة بداية، ثم فعّل أو ألغِ أي بند وغيّر أي خيار، وتتحدث المجاميع تلقائياً."},
    "start": {"en": "Start from", "ar": "ابدأ من"},
    "currency": {"en": "Currency", "ar": "العملة"},
    "total": {"en": "Estimated total", "ar": "الإجمالي التقديري"},
    "hardware": {"en": "Hardware", "ar": "المعدات"},
    "freight": {"en": "Freight + port tax", "ar": "الشحن + رسوم الميناء"},
    "install": {"en": "Installation", "ar": "التركيب"},
    "contingency": {"en": "Contingency", "ar": "احتياطي"},
    "by_phase": {"en": "By phase", "ar": "حسب المرحلة"},
    "map": {"en": "Where everything goes", "ar": "مكان تركيب كل شيء"},
    "map_hint": {"en": "Tap a valve, a sensor station or a building to see what goes there.", "ar": "اضغط على صمام أو محطة حساس أو مبنى لترى ما يُركّب هناك."},
    "items": {"en": "Build your list", "ar": "كوّن قائمتك"},
    "essential": {"en": "Essential", "ar": "أساسي للتشغيل"},
    "optional": {"en": "Optional", "ar": "اختياري"},
    "if_skipped": {"en": "If skipped", "ar": "عند الاستغناء عنه"},
    "zones": {"en": "Per-zone plan", "ar": "خطة كل منطقة"},
    "zones_note": {"en": "Valve size comes from each zone's peak flow; check it against the real pipe. Cable runs from the control room along the pipe trench, +15 %.",
                   "ar": "مقاس الصمام محسوب من أعلى تدفق للمنطقة؛ طابقه مع مقاس الأنبوب الفعلي. طول الكابل من غرفة التحكم على امتداد خندق الأنابيب مع زيادة 15%."},
    "plc": {"en": "Which controller", "ar": "أي وحدة تحكم"},
    "wiring": {"en": "How the valves are wired", "ar": "طريقة توصيل الصمامات"},
    "buying": {"en": "Buying and importing", "ar": "الشراء والاستيراد"},
    "survey": {"en": "Check on site before buying", "ar": "تحقق في الموقع قبل الشراء"},
    "future": {"en": "Later additions", "ar": "إضافات لاحقة"},
    "sources": {"en": "Sources", "ar": "المصادر"},
    "est": {"en": "estimate", "ar": "تقدير"},
    "src": {"en": "listing", "ar": "مصدر"},
    "valve": {"en": "Valve", "ar": "الصمام"},
    "cable": {"en": "Cable", "ar": "الكابل"},
    "sensors": {"en": "Soil sensors", "ar": "حساسات التربة"},
    "location": {"en": "Location", "ar": "الموقع"},
    "crop": {"en": "Crop", "ar": "المحصول"},
    "area": {"en": "Area", "ar": "المساحة"},
    "here": {"en": "Installed here", "ar": "يُركّب هنا"},
    "nothing_here": {"en": "Nothing selected for this spot.", "ar": "لا شيء مختار لهذا المكان."},
    "approve": {"en": "The bare minimum is a proposal: review the Essential items and tell me what to change.",
                "ar": "الحد الأدنى اقتراح: راجع البنود الأساسية وأخبرني بما تريد تغييره."},
    "price_note": {"en": "Prices are planning numbers from public listings (marked listing) or estimates. Get local quotes on the exact part numbers before buying.",
                   "ar": "الأسعار أرقام تخطيطية من قوائم منشورة (مصدر) أو تقديرات. اطلب عروض أسعار محلية على أرقام القطع نفسها قبل الشراء."},
    "legend_valve": {"en": "Zone valve", "ar": "صمام منطقة"},
    "legend_sensor": {"en": "Soil sensor station", "ar": "محطة حساس التربة"},
    "legend_cable": {"en": "Cable route", "ar": "مسار الكابل"},
    "legend_bldg": {"en": "C control room · W well · T tank · H head unit", "ar": "C غرفة التحكم · W البئر · T الخزان · H وحدة الرأس"},
    "routes_guess": {"en": "Pipe routes on the farm map are a best guess, so cable lengths and valve spots are estimates until confirmed on site.",
                     "ar": "مسارات الأنابيب في خريطة المزرعة تقديرية، لذا أطوال الكوابل ومواقع الصمامات تقديرية حتى تُؤكَّد في الموقع."},
    "lang": {"en": "العربية", "ar": "English"},
    "each": {"en": "each", "ar": "للوحدة"},
    "phase": {"en": "Phase", "ar": "المرحلة"},
    "zone_col": {"en": "Zone", "ar": "المنطقة"},
    "valve_ll": {"en": "Valve (lat, lon)", "ar": "موقع الصمام"},
    "station_ll": {"en": "Sensor station (lat, lon)", "ar": "موقع محطة الحساس"},
    "caps": {"en": "What this list gives you", "ar": "ما تحصل عليه بهذه القائمة"},
    "checks": {"en": "Check these choices", "ar": "راجع هذه الاختيارات"},
    "items_on": {"en": "Items", "ar": "عدد البنود"},
    "local_note": {"en": "Local labour: no freight or installation added.", "ar": "عمالة محلية: بلا شحن أو تركيب إضافي."},
    "override": {"en": "When something goes down", "ar": "عند تعطل أي جزء"},
    "install_mode": {"en": "Installation", "ar": "التركيب"},
    "install_contractor": {"en": "Contractor (15%)", "ar": "مقاول (15%)"},
    "install_own": {"en": "Own workers (5%)", "ar": "عمالك (5%)"},
    "connection": {"en": "Wireless option", "ar": "خيار لاسلكي"},
    "conn_cable": {"en": "Cable (near)", "ar": "كابل (قريبة)"},
    "conn_box": {"en": "Cable or radio box", "ar": "كابل أو صندوق لاسلكي"},
    "footer": {"en": "Generated from the farm's own map and zone data. Prices change often; treat every figure as a planning number.",
               "ar": "مولّد من خريطة المزرعة وبيانات مناطقها. الأسعار تتغير كثيراً؛ اعتبر كل رقم تقديراً للتخطيط."},
}

SUMMARY = [
    {"en": "Controller: <b>ET 200SP CPU 1512SP-1 PN</b> (S7-1500 family). OPC UA works in your TIA Portal V19 and PLCSIM Advanced simulates it, so the G5 tests carry over. For the bare minimum, the cheaper <b>S7-1200 1214C</b> also works with V19.",
     "ar": "وحدة التحكم: <b>ET 200SP CPU 1512SP-1 PN</b> من عائلة S7-1500. يعمل OPC UA في TIA Portal V19 لديك ويحاكيها PLCSIM Advanced، فتنتقل اختبارات G5 كما هي. وللحد الأدنى يعمل أيضاً <b>S7-1200 1214C</b> الأرخص مع V19."},
    {"en": "Valves: <b>buried 24 VAC cable in the existing pipe trenches</b> (about 800 m on three runs). Every valve stays under the PLC's interlocks and nothing in the field needs batteries.",
     "ar": "الصمامات: <b>كابل 24 فولت مدفون في خنادق الأنابيب الحالية</b> (نحو 800 م على ثلاثة مسارات). يبقى كل صمام تحت حمايات الـPLC ولا شيء في الحقل يحتاج بطاريات."},
    {"en": "Soil sensors: <b>wireless (LoRaWAN)</b>, 21 sensors at 12 stations and one gateway at the control room. No extra trenching.",
     "ar": "حساسات التربة: <b>لاسلكية (LoRaWAN)</b>، 21 حساساً في 12 محطة وبوابة واحدة في غرفة التحكم، بلا حفر إضافي."},
    {"en": "Head unit: a <b>speed drive on the booster</b>, an <b>electromagnetic flow meter</b>, a <b>pressure transmitter</b>, and a <b>level probe in the well</b> for steady pressure, water per zone, leak alarms and dry-run protection.",
     "ar": "وحدة الرأس: <b>منظّم سرعة لمضخة التعزيز</b>، <b>عداد تدفق كهرومغناطيسي</b>، <b>حساس ضغط</b>، و<b>حساس مستوى في البئر</b>، لضغط ثابت ومياه كل منطقة وإنذارات التسريب وحماية المضخة من التشغيل على الجاف."},
    {"en": "Internet: Starlink is not available in Libya (talks on hold), so remote access uses a <b>4G router with an outdoor antenna</b>. Test Libyana and Almadar signal at the control room first.",
     "ar": "الإنترنت: Starlink غير متاح في ليبيا (المفاوضات متوقفة)، لذا يتم الوصول عن بُعد عبر <b>راوتر 4G مع هوائي خارجي</b>. اختبر إشارة ليبيانا والمدار في غرفة التحكم أولاً."},
]

PLC_OPTIONS = [
    {"en": ("S7-1200 classic (CPU 1214C)", "Yes", "No", "≈ $650 + $100 license", "Cheapest Siemens choice with OPC UA in V19; phased out from 1 Nov 2026."),
     "ar": ("S7-1200 الحالي (CPU 1214C)", "نعم", "لا", "≈ 650$ + 100$ ترخيص", "أرخص خيار من Siemens مع OPC UA في V19؛ يتوقف إنتاجه من 1 نوفمبر 2026.")},
    {"en": ("S7-1200 G2", "Only from TIA V21", "No", "≈ $600–$860", "New generation; budget a TIA Portal upgrade."),
     "ar": ("S7-1200 G2", "فقط من TIA V21", "لا", "≈ 600–860$", "الجيل الجديد؛ احسب تكلفة ترقية TIA Portal.")},
    {"en": ("ET 200SP CPU 1512SP-1 PN", "Yes", "Yes", "≈ $1,100 + $250 license", "Recommended: matches G5 and your PLCSIM Advanced."),
     "ar": ("ET 200SP CPU 1512SP-1 PN", "نعم", "نعم", "≈ 1,100$ + 250$ ترخيص", "الموصى به: يطابق G5 وPLCSIM Advanced لديك.")},
    {"en": ("S7-1500 CPU 1511-1 PN", "Yes", "Yes", "≈ $1,000–$1,600 + $250 license", "Most expandable; built-in display."),
     "ar": ("S7-1500 CPU 1511-1 PN", "نعم", "نعم", "≈ 1,000–1,600$ + 250$ ترخيص", "الأكثر قابلية للتوسعة، مع شاشة مدمجة.")},
    {"en": ("LOGO! 8.4 / Delta AS", "No OPC UA (Modbus TCP)", "No", "≈ $450", "Cheap, but needs a Modbus adapter in the app."),
     "ar": ("LOGO! 8.4 / Delta AS", "لا OPC UA (Modbus TCP)", "لا", "≈ 450$", "رخيص، لكن يحتاج محوّل Modbus في التطبيق.")},
    {"en": ("Unitronics UniStream", "OPC UA built in", "No", "≈ $900", "Includes a touch screen; programmed outside TIA."),
     "ar": ("Unitronics UniStream", "OPC UA مدمج", "لا", "≈ 900$", "يتضمن شاشة لمس؛ يُبرمج خارج TIA.")},
]
PLC_HEAD = {"en": ("Controller", "OPC UA with your TIA V19", "PLCSIM Advanced", "Price", "Note"),
            "ar": ("وحدة التحكم", "OPC UA مع TIA V19 لديك", "PLCSIM Advanced", "السعر", "ملاحظة")}

WIRING = [
    {"en": ("Buried cable (recommended)", "≈ $2,000–$3,600", "Cheapest parts; no batteries; the PLC switches every valve, so interlocks always apply.", "Trench work; long cables need surge protection.", "Best for 12 valves within 300 m."),
     "ar": ("كابل مدفون (الموصى به)", "≈ 2,000–3,600$", "أرخص القطع؛ بلا بطاريات؛ الـPLC يشغّل كل صمام فتنطبق الحمايات دائماً.", "أعمال حفر؛ الكوابل الطويلة تحتاج حماية من الصواعق.", "الأفضل لـ12 صماماً ضمن 300 م.")},
    {"en": ("RS-485 remote I/O box", "≈ $600–$1,200 per box", "Fewer long cables; easy to add southern zones later.", "A powered box in the field to maintain.", "Good if zones are added in the south."),
     "ar": ("صندوق مداخل/مخارج بعيد RS-485", "≈ 600–1,200$ للصندوق", "كوابل طويلة أقل؛ سهولة إضافة مناطق جنوبية لاحقاً.", "صندوق مغذّى بالكهرباء في الحقل يحتاج صيانة.", "مناسب إن أُضيفت مناطق في الجنوب.")},
    {"en": ("Wireless valve controllers", "≈ $150–$385 per valve", "No trenching; quick to install.", "Batteries; valves outside the PLC's direct control; radio delays.", "Use wireless for sensors, not valves."),
     "ar": ("متحكمات صمامات لاسلكية", "≈ 150–385$ لكل صمام", "بلا حفر؛ تركيب سريع.", "بطاريات؛ الصمامات خارج تحكم الـPLC المباشر؛ تأخير لاسلكي.", "اللاسلكي للحساسات وليس للصمامات.")},
    {"en": ("Two-wire decoders", "≈ $150–$250 per decoder", "One cable for all valves.", "Needs the maker's controller; doesn't fit a PLC.", "Not recommended here."),
     "ar": ("نظام السلكين مع مفككات", "≈ 150–250$ للمفكك", "كابل واحد لكل الصمامات.", "يحتاج متحكم الشركة المصنعة؛ لا يناسب الـPLC.", "غير موصى به هنا.")},
]
WIRING_HEAD = {"en": ("Option", "Cost", "For", "Against", "Verdict"), "ar": ("الخيار", "التكلفة", "المزايا", "العيوب", "الحكم")}

BUYING = [
    {"en": "<b>Local (Tripoli, Misrata):</b> easiest warranty and support for Siemens parts and irrigation valves. Ask for quotes on the exact part numbers.",
     "ar": "<b>محلياً (طرابلس، مصراتة):</b> أسهل في الضمان والدعم لقطع Siemens وصمامات الري. اطلب عروضاً على أرقام القطع نفسها."},
    {"en": "<b>Import (Turkey, Tunisia, EU):</b> usually better prices for Siemens, Danfoss, Netafim and Bermad. Libya applies a 4% port services tax on the CIF value of most goods; sources disagree on further duties (0–25% by HS code), so confirm with a customs broker.",
     "ar": "<b>استيراد (تركيا، تونس، أوروبا):</b> أسعار أفضل عادةً لـSiemens وDanfoss وNetafim وBermad. تفرض ليبيا رسم خدمات موانئ 4% على قيمة CIF لمعظم البضائع، والمصادر تختلف حول رسوم إضافية (0–25% حسب رمز HS)، فتأكد مع مخلّص جمركي."},
    {"en": "<b>China direct:</b> good value for flow meters, generic transmitters and LoRaWAN sensors. Buy one sample first and check its documentation: Modbus register map, IP rating, cable length.",
     "ar": "<b>من الصين مباشرة:</b> قيمة جيدة لعدادات التدفق والحساسات العامة وحساسات LoRaWAN. اشترِ عينة واحدة أولاً وتحقق من وثائقها: خريطة سجلات Modbus، درجة الحماية IP، طول الكابل."},
]
SURVEY = [
    {"en": "Pump nameplates: well pump and booster kW/HP, voltage, current; well depth and pump depth.", "ar": "لوحات بيانات المضخات: قدرة مضخة البئر ومضخة التعزيز، الجهد، التيار؛ عمق البئر وعمق المضخة."},
    {"en": "Valve and pipe sizes at each zone's take-off.", "ar": "مقاسات الصمامات والأنابيب عند تفرّع كل منطقة."},
    {"en": "Real pipe routes (the map's routes are a best guess, and cable lengths follow them).", "ar": "مسارات الأنابيب الفعلية (مسارات الخريطة تقديرية وأطوال الكوابل تتبعها)."},
    {"en": "4G signal at the control room for Libyana and Almadar (a phone speed test is enough).", "ar": "إشارة 4G في غرفة التحكم لليبيانا والمدار (يكفي اختبار سرعة من الهاتف)."},
    {"en": "The existing filter at the head unit and a spot for the fertilizer tank.", "ar": "الفلتر الحالي عند وحدة الرأس ومكان لخزان السماد."},
    {"en": "The farm gate position (for a camera) and space for solar panels near the control room.", "ar": "موقع بوابة المزرعة (لكاميرا) ومساحة للألواح الشمسية قرب غرفة التحكم."},
]
FUTURE = [
    {"en": ("On-farm weather station", "The farm's own rain and wind instead of a forecast grid point.", "≈ $700–$1,500"),
     "ar": ("محطة طقس في المزرعة", "مطر ورياح المزرعة نفسها بدل نقطة توقعات عامة.", "≈ 700–1,500$")},
    {"en": ("Flow meter per zone", "Exact water per zone, even with two zones running.", "≈ $150–$460 per zone"),
     "ar": ("عداد تدفق لكل منطقة", "مياه كل منطقة بدقة حتى مع تشغيل منطقتين.", "≈ 150–460$ للمنطقة")},
    {"en": ("Pressure at the end of the drip lines", "Confirms water reaches the last tree.", "≈ $150 per zone"),
     "ar": ("ضغط في نهاية خطوط التنقيط", "يؤكد وصول الماء لآخر شجرة.", "≈ 150$ للمنطقة")},
    {"en": ("Hosting with HTTPS", "Needed for phone notifications on phones and safe outside access.", "≈ $5–$15 per month"),
     "ar": ("استضافة مع HTTPS", "تلزم لإشعارات الهاتف والوصول الآمن من الخارج.", "≈ 5–15$ شهرياً")},
    {"en": ("Crop health maps (drone or satellite)", "Spot stressed trees early.", "Service"),
     "ar": ("خرائط صحة المحصول (درون أو قمر صناعي)", "اكتشاف الأشجار المجهدة مبكراً.", "خدمة")},
    {"en": ("Standby pump", "Automatic changeover if the well pump fails in summer.", "Depends on pump"),
     "ar": ("مضخة احتياطية", "تبديل تلقائي إذا تعطلت مضخة البئر صيفاً.", "حسب المضخة")},
]
FUTURE_HEAD = {"en": ("Idea", "Why", "Rough cost"), "ar": ("الفكرة", "الفائدة", "التكلفة التقريبية")}


# "What this list gives you": a capability is on when every group in `need` has at least one item ticked
CAPS = [
    {"need": [["cpu"], ["io"], ["server"], ["trafo"], ["v2", "v15", "v1"], ["vcable", "wireless_valves"], ["starters", "vfd"]],
     "en": "Automatic irrigation of the 12 zones from the app", "ar": "ري تلقائي للمناطق الـ12 من التطبيق"},
    {"need": [["estop"]], "en": "Emergency stop at the panel", "ar": "إيقاف طوارئ على اللوحة"},
    {"need": [["override"]], "en": "Manual override if the PLC, app or internet is down", "ar": "تشغيل يدوي إذا توقف الـPLC أو التطبيق أو الإنترنت"},
    {"need": [["tanklevel"], ["flow"], ["pressure"]], "en": "Safety interlocks: low tank, no flow, pressure out of range", "ar": "حمايات السلامة: خزان منخفض، لا تدفق، ضغط خارج النطاق"},
    {"need": [["flow"]], "en": "Water used per zone and leak alarms", "ar": "مياه كل منطقة وإنذارات التسريب"},
    {"need": [["pumpprot", "welllevel"]], "en": "Well pump protected from running dry", "ar": "حماية مضخة البئر من التشغيل على الجاف"},
    {"need": [["router"]], "en": "Use the app away from the farm", "ar": "استخدام التطبيق من خارج المزرعة"},
    {"need": [["soil"]], "en": "Irrigation based on measured soil water", "ar": "ري حسب رطوبة التربة المقاسة"},
    {"need": [["vfd"]], "en": "Steady pressure and lower pump energy", "ar": "ضغط ثابت وطاقة أقل للمضخة"},
    {"need": [["meter"]], "en": "Energy use per pump (early warning of a failing pump)", "ar": "استهلاك كهرباء كل مضخة (إنذار مبكر بتعطلها)"},
    {"need": [["ups"]], "en": "Keeps running through short power cuts", "ar": "يستمر العمل خلال انقطاعات الكهرباء القصيرة"},
    {"need": [["dp"]], "en": "Filter clogging alarm", "ar": "إنذار انسداد الفلتر"},
    {"need": [["fert"]], "en": "Fertilizer through the drip lines", "ar": "التسميد مع الري"},
    {"need": [["cams", "cam4g"]], "en": "Video of the farm on the phone", "ar": "فيديو المزرعة على الهاتف"},
    {"need": [["solar"]], "en": "Solar power for the well pump", "ar": "طاقة شمسية لمضخة البئر"},
]

S1500 = ["et200sp", "s71511"]
S1200 = ["s71200", "g2", "used1200"]
# each check: `when` is a list of conditions [item, "on"|"off"|option keys...]; all must hold
CHECKS = [
    {"when": [["soil", "rec", "prem"], ["gateway", "off"]], "en": "Wireless soil sensors need the LoRaWAN gateway.", "ar": "حساسات التربة اللاسلكية تحتاج بوابة LoRaWAN."},
    {"when": [["soil", "basic"], ["rs485", "off"]], "en": "Wired soil sensors need the RS-485 port.", "ar": "حساسات التربة السلكية تحتاج منفذ RS-485."},
    {"when": [["meter", "on"], ["rs485", "off"]], "en": "Energy meters need the RS-485 port.", "ar": "عدادات الكهرباء تحتاج منفذ RS-485."},
    {"when": [["cpu", *S1500], ["mc", "off"]], "en": "S7-1500 family controllers need the memory card.", "ar": "وحدات عائلة S7-1500 تحتاج بطاقة الذاكرة."},
    {"when": [["cpu", *S1200], ["io", "rec", "prem"]], "en": "The I/O modules don't match the controller: pick the S7-1200 modules.", "ar": "وحدات المداخل والمخارج لا تناسب وحدة التحكم: اختر وحدات S7-1200."},
    {"when": [["cpu", *S1500], ["io", "min", "basic"]], "en": "The I/O modules don't match the controller: pick the ET 200SP or S7-1500 modules.", "ar": "وحدات المداخل والمخارج لا تناسب وحدة التحكم: اختر وحدات ET 200SP أو S7-1500."},
    {"when": [["cpu", *S1200], ["opcua", "s71500"]], "en": "The OPC UA license must be the S7-1200 one.", "ar": "ترخيص OPC UA يجب أن يكون الخاص بـS7-1200."},
    {"when": [["cpu", *S1500], ["opcua", "s71200"]], "en": "The OPC UA license must be the S7-1500 one.", "ar": "ترخيص OPC UA يجب أن يكون الخاص بـS7-1500."},
    {"when": [["cpu", "smart200"]], "en": "The S7-200 SMART needs a Modbus TCP adapter in the app first, needs no OPC UA license, and its I/O is in the CPU option.", "ar": "يحتاج S7-200 SMART أولاً محوّل Modbus TCP في التطبيق، ولا يحتاج ترخيص OPC UA، ومداخله ومخارجه ضمن خيار الوحدة."},
    {"when": [["cpu", "used1200", "s71200", "g2"], ["opcua", "off"]], "en": "The S7-1200 needs the OPC UA license for the app to connect.", "ar": "يحتاج S7-1200 ترخيص OPC UA ليتصل التطبيق."},
    {"when": [["wireless_valves", "boxes"], ["rs485", "off"]], "en": "The radio boxes need the RS-485 port on the PLC.", "ar": "الصناديق اللاسلكية تحتاج منفذ RS-485 على الـPLC."},
    {"when": [["wireless_valves", "uc511"], ["gateway", "off"]], "en": "LoRaWAN valve controllers need the LoRaWAN gateway.", "ar": "متحكمات الصمامات LoRaWAN تحتاج بوابة LoRaWAN."},
    {"when": [["vcable", "near"], ["wireless_valves", "off"]], "en": "With cable to the near zones only, the 6 far zones need the wireless boxes.", "ar": "مع كابل للمناطق القريبة فقط، تحتاج المناطق الست البعيدة الصناديق اللاسلكية."},
    {"when": [["vcable", "min", "rec", "prem", "mixed"], ["wireless_valves", "boxes"]], "en": "The cable already reaches every zone; pick 'near zones only' cable or drop the radio boxes.", "ar": "الكابل يصل لكل المناطق أصلاً؛ اختر كابل المناطق القريبة فقط أو احذف الصناديق اللاسلكية."},
    {"when": [["cpu", "logo", "delta"]], "en": "LOGO! and Delta need a Modbus TCP adapter in the app before they can be used, and they need no OPC UA license.", "ar": "LOGO! وDelta يحتاجان محوّل Modbus TCP في التطبيق قبل استخدامهما، ولا يحتاجان ترخيص OPC UA."},
    {"when": [["cpu", "g2"]], "en": "The S7-1200 G2 OPC UA server needs TIA Portal V21; you have V19.", "ar": "خادم OPC UA في S7-1200 G2 يحتاج TIA Portal V21، ولديك V19."},
    {"when": [["vcable", "min", "rec", "prem", "mixed"], ["wireless_valves", "uc511"]], "en": "You picked both cable and wireless valve controllers; one is enough.", "ar": "اخترت الكابل والمتحكمات اللاسلكية معاً؛ يكفي أحدهما."},
    {"when": [["vcable", "off"], ["wireless_valves", "off"]], "en": "The valves have no connection: pick the cable or the wireless controllers.", "ar": "الصمامات بلا توصيل: اختر الكابل أو المتحكمات اللاسلكية."},
    {"when": [["starters", "off"], ["vfd", "off"]], "en": "The PLC can't start the pumps without starters or a drive.", "ar": "لا يستطيع الـPLC تشغيل المضخات دون مشغّلات أو منظّم سرعة."},
    {"when": [["solar", "on"], ["vfd", "both"]], "en": "With solar, the solar inverter already drives the well pump; one G120X (booster) is enough.", "ar": "مع الطاقة الشمسية يشغّل العاكس الشمسي مضخة البئر؛ يكفي G120X واحد لمضخة التعزيز."},
    {"when": [["solar", "off"], ["starters", "off"], ["vfd", "rec", "prem"]], "en": "Without solar, the well pump needs a starter (or a second drive).", "ar": "بدون الطاقة الشمسية تحتاج مضخة البئر مشغّلاً (أو منظّم سرعة ثانياً)."},
    {"when": [["vfd", "rec", "prem"], ["starters", "two"]], "en": "The booster runs on its drive, so one starter (well pump) is enough.", "ar": "مضخة التعزيز تعمل بمنظّم السرعة، فيكفي مشغّل واحد لمضخة البئر."},
]


OVERRIDE = [
    {"en": ("Internet down", "The app keeps working on the farm Wi-Fi and the schedules keep running on the farm server. Remote access returns with the internet.", "Nothing to do."),
     "ar": ("انقطاع الإنترنت", "يستمر التطبيق على شبكة Wi-Fi المزرعة وتستمر الجداول على خادم المزرعة. يعود الوصول عن بُعد مع عودة الإنترنت.", "لا شيء.")},
    {"en": ("Farm server or app down", "The PLC keeps every safety interlock. In G5 the PLC also keeps a copy of today's program, so irrigation goes on.", "Restart the server; meanwhile use the zone switches on the panel."),
     "ar": ("توقف خادم المزرعة أو التطبيق", "يحتفظ الـPLC بكل حمايات السلامة. وفي G5 يحتفظ الـPLC أيضاً بنسخة من برنامج اليوم فيستمر الري.", "أعد تشغيل الخادم؛ وفي الأثناء استخدم مفاتيح المناطق على اللوحة.")},
    {"en": ("PLC down", "Automatic irrigation stops; the pump protection relay still works.", "Turn the pump and zone switches to Hand and watch the pressure gauge; or open valves by their manual screw."),
     "ar": ("توقف الـPLC", "يتوقف الري التلقائي؛ يبقى مرحّل حماية المضخة يعمل.", "حوّل مفاتيح المضخة والمناطق إلى يدوي وراقب مقياس الضغط؛ أو افتح الصمامات ببرغيها اليدوي.")},
    {"en": ("Power cut", "Pumps stop (no power to pump). With backup power the PLC and server stay on and show what happened; with solar the well pump runs by day.", "Nothing to do; everything restarts by itself."),
     "ar": ("انقطاع الكهرباء", "تتوقف المضخات (لا كهرباء). مع الطاقة الاحتياطية يبقى الـPLC والخادم يعملان ويعرضان ما حدث؛ ومع الطاقة الشمسية تعمل مضخة البئر نهاراً.", "لا شيء؛ كل شيء يعود للعمل وحده.")},
    {"en": ("Valve coil or cable fault", "The PLC sees no flow and raises an alarm for that zone.", "Open or close that valve by its manual screw until it is fixed."),
     "ar": ("عطل في ملف الصمام أو الكابل", "لا يرى الـPLC تدفقاً ويطلق إنذاراً لتلك المنطقة.", "افتح أو أغلق ذلك الصمام ببرغيه اليدوي حتى الإصلاح.")},
    {"en": ("Sensor fault (flow, pressure, tank)", "The app shows the fault and the PLC blocks automatic runs that depend on it.", "Run zones in Hand on the panel while watching the pressure gauge, until the sensor is replaced."),
     "ar": ("عطل حساس (تدفق، ضغط، خزان)", "يعرض التطبيق العطل ويمنع الـPLC التشغيل التلقائي المعتمد عليه.", "شغّل المناطق يدوياً من اللوحة مع مراقبة مقياس الضغط حتى استبدال الحساس.")},
    {"en": ("Wireless box or radio down", "Its valves close by themselves when their on-timer runs out.", "Use the manual switch inside the box or the valve's manual screw."),
     "ar": ("توقف صندوق لاسلكي أو الراديو", "تُغلق صماماته وحدها عند انتهاء مؤقت التشغيل.", "استخدم المفتاح اليدوي داخل الصندوق أو البرغي اليدوي للصمام.")},
]
OVERRIDE_HEAD = {"en": ("If this fails", "What happens", "How to override"), "ar": ("إذا تعطل", "ماذا يحدث", "كيف تتجاوزه يدوياً")}
