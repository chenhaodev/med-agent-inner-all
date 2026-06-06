#!/usr/bin/env python3
"""
apply_gap_entries.py — 将经过人工核验的 COVERAGE_GAP 条目写入各 YAML 文件

每个条目：
  - folio 已从源文件验证
  - key_points 基于源文内容人工撰写，患者向表述
  - 跳过假阳性（如 MMC"运动"、神经"运动功能"等）

用法：python3 bin/apply_gap_entries.py [--dry-run]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
import yaml

# ── 所有待添加的条目 (specialty, disease, entry_dict) ────────────
ENTRIES: list[tuple[str, str, dict]] = [

    # ── bone_mineral ──────────────────────────────────────────────
    ("bone_mineral", "metabolic_bone", {
        "id": "BM_METABOLIC_EXERCISE",
        "title": "代谢性骨病与体力活动",
        "source_page": 817,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "体力活动不足和营养不良可促进骨骼去矿化，增加代谢性骨病和骨折风险",
            "终末期肺、心脏或肾脏疾病患者因活动减少，骨量丢失风险显著升高",
            "在病情允许时维持适量体力活动有助于延缓骨量丢失",
        ],
        "pdf_page": 206,
    }),

    ("bone_mineral", "osteoporosis", {
        "id": "BM_OSTEO_LIFESTYLE",
        "title": "骨质疏松生活方式管理",
        "source_page": 823,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "充足的钙和维生素D摄入、适量体力活动及预防跌倒是所有骨质疏松患者的基础措施",
            "美国国家医学研究院推荐成人每日元素钙摄入量为1200mg，来源包括饮食和补充剂",
            "负重运动（如步行、太极）可维持骨密度，同时改善平衡功能以预防跌倒骨折",
        ],
        "pdf_page": 212,
    }),

    # ── cardiology ────────────────────────────────────────────────
    ("cardiology", "arrhythmia", {
        "id": "CARD_ARR_EXERCISE",
        "title": "心律失常患者的运动注意事项",
        "source_page": 140,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "部分遗传性心律失常（如LQT1型）在运动或高肾上腺素状态下危险度增加",
            "心律失常患者运动强度和类型需经医生评估，不可自行判断运动安全性",
            "植入起搏器或除颤器的患者应遵循医嘱决定可参与的运动项目",
        ],
        "pdf_page": 161,
    }),

    ("cardiology", "cad", {
        "id": "CARD_CAD_EXERCISE",
        "title": "冠心病与体力活动",
        "source_page": 96,
        "evidence_level": "高",
        "recommendation": "建议",
        "key_points": [
            "体力活动是稳定型心绞痛的常见诱因，活动中出现胸痛或胸闷应立即停止活动并休息",
            "含服硝酸甘油可在数分钟内缓解活动诱发的心绞痛，随身携带并了解正确使用方法",
            "经治疗后症状稳定的冠心病患者在医生指导下可进行适量有氧运动",
        ],
        "pdf_page": 117,
    }),

    ("cardiology", "cad", {
        "id": "CARD_CAD_REHAB",
        "title": "冠心病心脏康复",
        "source_page": 115,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "心肌梗死后应积极开展患者教育，使患者充分了解治疗价值及冠心病危险因素控制",
            "心脏康复计划包括运动训练、危险因素管理（戒烟、血压、血糖、血脂控制）和心理支持",
            "参与规范心脏康复计划可显著降低再次心肌梗死和心血管死亡风险",
        ],
        "pdf_page": 136,
    }),

    ("cardiology", "heart_failure", {
        "id": "CARD_HF_EXERCISE",
        "title": "心力衰竭与体力活动耐量",
        "source_page": 58,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "心功能NYHA I级患者体力活动不受限；II级患者日常活动引起轻度症状；III-IV级时活动明显受限",
            "心力衰竭患者应根据心功能分级调整日常活动强度，避免超出耐受范围",
            "病情稳定的轻中度心衰患者在医生指导下进行适量有氧运动可改善运动耐量",
        ],
        "pdf_page": 79,
    }),

    ("cardiology", "heart_failure", {
        "id": "CARD_HF_DIET",
        "title": "心力衰竭饮食管理",
        "source_page": 65,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "饮食中钠（盐）和液体过量摄入是心力衰竭急性加重的常见诱因",
            "心衰患者通常需要限制每日食盐摄入（一般建议每日钠摄入＜2g），并监测液体出入量",
            "出现体重短期内快速增加（如3天内增加2kg以上）提示液体潴留，应及时就医",
        ],
        "pdf_page": 86,
    }),

    # ── digestive ─────────────────────────────────────────────────
    ("digestive", "liver", {
        "id": "DIG_LIVER_DIET",
        "title": "肝硬化腹水饮食管理",
        "source_page": 502,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "肝硬化腹水患者应限制饮食钠摄入，同时配合利尿剂治疗以减轻腹水和水肿",
            "限钠饮食是腹水的一线非药物治疗措施，严重腹水时可能需要利尿剂联合大量腹腔穿刺引流",
            "肝功能严重受损时还需注意蛋白质摄入量，避免过度限制导致营养不良",
        ],
        "pdf_page": 521,
    }),

    ("digestive", "liver", {
        "id": "DIG_LIVER_REHAB",
        "title": "药物性肝损伤康复要点",
        "source_page": 485,
        "evidence_level": "中",
        "recommendation": "强推荐",
        "key_points": [
            "轻至中度药物性肝损伤（DILI）在及时停用相关药物后通常能够自行康复",
            "康复期间应避免再次接触可疑肝毒性药物，避免饮酒，定期复查肝功能",
            "部分DILI有特异性解毒剂（如对乙酰氨基酚中毒用N-乙酰半胱氨酸），应由医生决定",
        ],
        "pdf_page": 504,
    }),

    # ── endocrine ─────────────────────────────────────────────────
    ("endocrine", "obesity", {
        "id": "ENDO_OBE_EXERCISE",
        "title": "肥胖症体力活动管理",
        "source_page": 732,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "有效的生活方式干预包括膳食结构调整和个体化体力活动方案两个核心部分",
            "行为矫正和患者教育是实现目标体重和长期维持减重效果的重要手段",
            "建议在专业人员指导下制定适合个人身体状况的运动计划，逐步增加活动量",
        ],
        "pdf_page": 122,
    }),

    ("endocrine", "thyroid", {
        "id": "ENDO_THYROID_DIET",
        "title": "甲状腺疾病饮食注意事项",
        "source_page": 687,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "有甲状腺肿的患者在饮食碘摄入量突然增加时（如大量食用海产品或使用含碘造影剂）可能诱发甲亢",
            "甲状腺疾病患者在进行需要碘造影剂的检查前应告知医生甲状腺病史",
            "甲状腺功能减退患者服用左甲状腺素应在空腹时服用，避免与高纤维饮食或钙剂同时服用",
        ],
        "pdf_page": 77,
    }),

    # ── geriatrics ────────────────────────────────────────────────
    ("geriatrics", "elderly_care", {
        "id": "GER_EXERCISE",
        "title": "老年人运动能力与跌倒预防",
        "source_page": 1214,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "步速是衡量老年人运动能力和整体健康状况的重要指标，步速减慢提示跌倒和功能下降风险增加",
            "计时起立行走测试（TUG）超过12秒提示跌倒风险显著增加，应进行专科评估",
            "规律的平衡训练、力量锻炼（如太极、步行）可降低跌倒风险，改善老年人功能状态",
        ],
        "pdf_page": 601,
    }),

    ("geriatrics", "elderly_care", {
        "id": "GER_DIET",
        "title": "老年人营养与饮食管理",
        "source_page": 1216,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "老年患者应评估吞咽功能，有吞咽困难者需调整饮食质地（软食/流质）以预防误吸",
            "营养不良在老年人中常见，可影响功能康复速度和住院预后",
            "既往饮食限制（如低盐、低蛋白）在老年阶段需重新评估，过度限制可能加重营养不良",
        ],
        "pdf_page": 603,
    }),

    ("geriatrics", "elderly_care", {
        "id": "GER_REHAB",
        "title": "老年人急性期后康复",
        "source_page": 1218,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "老年评估管理（GEM）单元提供专业的、多学科团队协作的急性期后康复",
            "康复目标是帮助患者尽可能恢复到患病前的功能水平，包括日常生活能力和行动能力",
            "早期启动康复（住院期间即开始）比延迟康复能获得更好的功能恢复结果",
        ],
        "pdf_page": 605,
    }),

    ("geriatrics", "elderly_care", {
        "id": "GER_HOME_CARE",
        "title": "老年人居家护理要点",
        "source_page": 1219,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "居家护理和个人护理服务（如助浴、送餐、家政）是维持老年人社区独立生活的重要支持",
            "家庭照护者需了解患者的护理需求，必要时申请专业居家护理机构的支持",
            "出院前应评估家庭环境安全（如防滑、扶手、照明），并做好家庭改造以预防跌倒",
        ],
        "pdf_page": 606,
    }),

    # ── infectious ────────────────────────────────────────────────
    ("infectious", "general", {
        "id": "INF_REHAB",
        "title": "严重感染后康复",
        "source_page": 925,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "严重感染（如细菌性脑膜炎、败血症）患者急性期治疗后可能需要在专业机构进行长期康复护理",
            "部分患者可能留有永久性残疾（如肾功能损伤、神经功能障碍），康复目标应个体化",
            "家属应了解康复是一个长期过程，出院后仍需持续随访和功能训练",
        ],
        "pdf_page": 313,
    }),

    # ── mens_health ───────────────────────────────────────────────
    ("mens_health", "mens_health", {
        "id": "MH_LIFESTYLE",
        "title": "男性健康生活方式建议",
        "source_page": 786,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "减小压力、改善睡眠及健康饮食均可改善男性生育能力和整体健康状况",
            "以维生素和膳食抗氧化物为主的营养干预可能有助于改善精子活动度和质量",
            "避免高温环境（如长期泡热水澡、桑拿）有助于维持精子正常生成",
        ],
        "pdf_page": 175,
    }),

    # ── neurology ─────────────────────────────────────────────────
    ("neurology", "epilepsy", {
        "id": "NEURO_EPI_DIET",
        "title": "癫痫饮食治疗（生酮饮食）",
        "source_page": 1157,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "生酮饮食（极高脂肪、低碳水化合物和蛋白质）可减少部分儿童和成人癫痫患者的发作频率",
            "生酮饮食需在专业营养师和神经科医生指导下进行，不可自行实施",
            "通常用于2种以上抗癫痫药物治疗无效的难治性癫痫患者",
        ],
        "pdf_page": 545,
    }),

    ("neurology", "epilepsy", {
        "id": "NEURO_EPI_ALCOHOL",
        "title": "癫痫患者戒酒建议",
        "source_page": 1147,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "戒酒过程中（酒精戒断）可诱发癫痫发作，有癫痫病史的患者应完全戒酒",
            "大量饮酒本身和饮酒后睡眠剥夺均可降低癫痫发作阈值",
            "服用抗癫痫药物期间饮酒可能影响药物代谢，增加毒副作用风险",
        ],
        "pdf_page": 535,
    }),

    ("neurology", "stroke", {
        "id": "NEURO_STROKE_EXERCISE",
        "title": "脑卒中预防与体力活动",
        "source_page": 1129,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "缺乏体力活动是脑卒中的独立危险因素，规律有氧运动有助于降低卒中风险",
            "运动可改善血压、血脂、血糖等多种卒中危险因素，建议每周至少150分钟中等强度运动",
            "已发生过TIA或卒中的患者应在医生评估后进行适量运动，避免高强度剧烈运动",
        ],
        "pdf_page": 517,
    }),

    ("neurology", "stroke", {
        "id": "NEURO_STROKE_REHAB",
        "title": "脑卒中康复",
        "source_page": 1138,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "由理疗师和物理康复治疗师组成的专业卒中康复单元对患者功能恢复有重要意义",
            "卒中康复应尽早启动（病情稳定后48小时内），早期康复可改善运动、语言和认知功能",
            "卒中后康复是长期过程，出院后仍需继续门诊或居家康复训练",
        ],
        "pdf_page": 526,
    }),

    # ── palliative ────────────────────────────────────────────────
    ("palliative", "palliative_care", {
        "id": "PAL_DIET",
        "title": "临终期饮食与营养支持",
        "source_page": 1228,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "临终期患者食物和液体摄入量逐渐减少是自然衰退过程，大多数患者不会感到饥饿或口渴",
            "不应强迫临终患者进食，人工营养（鼻饲/静脉营养）在临终阶段通常不能改善舒适度",
            "少量口腔护理（湿润口腔）可缓解口干不适，比强制进食更能提高舒适度",
        ],
        "pdf_page": 615,
    }),

    ("palliative", "palliative_care", {
        "id": "PAL_HOME_CARE",
        "title": "姑息治疗与家庭护理",
        "source_page": 1222,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "姑息治疗可在多种机构提供，包括医院、家庭护理、养老院及门诊，患者可根据需求选择",
            "家庭护理模式允许患者在熟悉的环境中接受专业医疗护理和症状管理",
            "家属是家庭护理的重要参与者，需了解护理技能（如皮肤护理、口腔护理、体位变换）及如何呼叫专业支持",
        ],
        "pdf_page": 609,
    }),

    # ── renal ─────────────────────────────────────────────────────
    ("renal", "ckd", {
        "id": "REN_CKD_SMOKING",
        "title": "慢性肾病患者戒烟",
        "source_page": 389,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "戒烟是慢性肾病管理的重要措施，与控制高血压、糖尿病等危险因素并列",
            "吸烟可加速肾功能下降，增加终末期肾病风险",
            "同时需应用RAAS阻断药物（如普利类或沙坦类）并调整饮食，共同延缓肾功能进展",
        ],
        "pdf_page": 410,
    }),

    ("renal", "ckd", {
        "id": "REN_CKD_REHAB",
        "title": "慢性肾病肾移植与康复",
        "source_page": 390,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "符合条件的慢性肾病患者应鼓励考虑肾移植，移植可提供比透析更好的生活质量和更高的生存率",
            "成功肾移植后患者有更多的康复机会，能够恢复更接近正常的生活和工作能力",
            "移植等待期间仍需维持透析治疗并积极管理并发症，保持身体状况以备移植",
        ],
        "pdf_page": 411,
    }),

    # ── respiratory ───────────────────────────────────────────────
    ("respiratory", "asthma", {
        "id": "RESP_ASTHMA_SMOKING",
        "title": "呼吸道疾病患者戒烟",
        "source_page": 225,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "吸烟是慢阻肺最主要的病因，也会加重哮喘症状；戒烟是预防和控制慢性气道疾病的首要措施",
            "任何年龄、任何阶段戒烟均可延缓肺功能下降，戒烟效果因人而异但均有益",
            "戒烟支持包括行为干预和药物辅助（如尼古丁替代疗法、伐尼克兰），可提高戒烟成功率",
        ],
        "pdf_page": 246,
    }),

    ("respiratory", "asthma", {
        "id": "RESP_PULM_REHAB",
        "title": "慢性肺病肺康复",
        "source_page": 227,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "综合性肺康复计划可改善慢性肺病患者的生活质量并减少主观呼吸困难感（1级证据）",
            "肺康复包括运动训练、呼吸技巧、营养支持和心理支持，通常持续8-12周",
            "肺康复不能替代药物治疗，但可显著提高患者的运动耐量和日常生活能力",
        ],
        "pdf_page": 248,
    }),

    # ── rheumatology ──────────────────────────────────────────────
    ("rheumatology", "osteoporosis", {
        "id": "RHE_OSTEO_LIFESTYLE",
        "title": "骨质疏松生活方式管理",
        "source_page": 823,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "充足的钙和维生素D摄入、适量体力活动及预防跌倒是骨质疏松患者的基础管理措施",
            "负重运动（如步行、太极、力量训练）可维持骨密度并改善平衡功能，降低跌倒骨折风险",
            "戒烟、限酒（主动和被动吸烟均有害骨骼），以及减少引起骨量丢失的药物（如激素）使用",
        ],
        "pdf_page": 212,
    }),

    ("rheumatology", "sle", {
        "id": "RHE_SLE_EXERCISE",
        "title": "系统性红斑狼疮体力活动建议",
        "source_page": 850,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "SLE的疲劳和关节症状可能限制体力活动，导致骨强度降低，增加骨质疏松风险",
            "病情稳定期应在医生指导下进行适量运动，有助于维持骨密度和整体体能",
            "避免阳光直射（SLE患者对紫外线敏感），户外运动时应做好防晒措施",
        ],
        "pdf_page": 239,
    }),

    # ── substance_use ─────────────────────────────────────────────
    ("substance_use", "alcohol_drugs", {
        "id": "SUB_ALCOHOL_DIET",
        "title": "酒精相关疾病营养管理",
        "source_page": 1233,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "酒精本身缺乏蛋白质、矿物质和维生素；长期大量饮酒者常合并严重营养不良",
            "初始治疗必须补充硫胺素（维生素B1），预防Wernicke脑病；同时纠正钾、镁、钙、锌缺乏",
            "戒酒后饮食应逐步恢复均衡营养，必要时在营养师指导下制定补充方案",
        ],
        "pdf_page": 619,
    }),

    ("substance_use", "alcohol_drugs", {
        "id": "SUB_ALCOHOL_ABSTAIN",
        "title": "酒精相关疾病戒酒建议",
        "source_page": 1238,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "有酒精滥用史或严重器官损害（如肝病）的患者应完全戒酒，而非仅减少饮酒量",
            "安全驾驶等公共安全场合禁止饮酒，酒后驾车危害生命",
            "戒酒过程中可能出现戒断症状（震颤、出汗、癫痫发作），戒断反应严重者需医疗监护",
        ],
        "pdf_page": 624,
    }),

    ("substance_use", "alcohol_drugs", {
        "id": "SUB_ALCOHOL_REHAB",
        "title": "酒精相关疾病康复治疗",
        "source_page": 1241,
        "evidence_level": "高",
        "recommendation": "强推荐",
        "key_points": [
            "药物治疗（如纳曲酮、阿坎酸）需与心理治疗和结构化康复治疗联用，以达到最佳疗效",
            "纳曲酮仅在患者完全解毒（戒断完成）后才能使用，使用前须确认无阿片类药物依赖",
            "社会支持和自助团体（如匿名戒酒会）是长期维持戒酒的重要辅助手段",
        ],
        "pdf_page": 627,
    }),

    # ── womens_health ─────────────────────────────────────────────
    ("womens_health", "womens_health", {
        "id": "WH_EXERCISE",
        "title": "女性健康与运动",
        "source_page": 756,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "女性中缺乏运动的比例较高，规律有氧运动有助于维持心血管健康、骨密度和整体健康",
            "过度运动或体重过低可导致功能性下丘脑性闭经，影响月经周期和生育能力，需评估运动强度",
            "运动强度和频率应根据个人健康状况、年龄和生命阶段（如妊娠、更年期）进行调整",
        ],
        "pdf_page": 146,
    }),

    ("womens_health", "womens_health", {
        "id": "WH_DIET",
        "title": "女性健康饮食管理",
        "source_page": 768,
        "evidence_level": "中",
        "recommendation": "建议",
        "key_points": [
            "包括药物及强调饮食和心理社会因素干预在内的多学科方案，对女性特有健康问题效果优于单纯药物治疗",
            "女性应注意铁、钙、叶酸的充足摄入，特别是在育龄期和更年期前后",
            "限制高糖、高脂饮食，维持健康体重，有助于降低多囊卵巢综合征、乳腺癌等风险",
        ],
        "pdf_page": 158,
    }),
]


# ── YAML 读写工具 ─────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    lines = []
    for key in ("specialty", "specialty_zh", "disease", "disease_zh", "source"):
        if key in data:
            lines.append(f"{key}: {data[key]}")
    lines.append("entries:")
    for entry in data.get("entries", []):
        lines.append(f"- id: {entry['id']}")
        lines.append(f"  title: {entry['title']}")
        lines.append(f"  source_page: {entry['source_page']}")
        lines.append(f"  evidence_level: {entry.get('evidence_level', '未注明')}")
        lines.append(f"  recommendation: {entry.get('recommendation', '未注明')}")
        lines.append("  key_points:")
        for kp in entry.get("key_points", []):
            lines.append(f"  - {kp}")
        if "pdf_page" in entry:
            lines.append(f"  pdf_page: {entry['pdf_page']}")
        if "must_warn" in entry:
            lines.append("  must_warn:")
            for w in entry["must_warn"]:
                lines.append(f"  - {w}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def entry_id_exists(data: dict, eid: str) -> bool:
    return any(e.get("id") == eid for e in data.get("entries", []))


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    total = 0
    by_file: dict[Path, list[dict]] = {}

    for specialty, disease, entry in ENTRIES:
        yaml_path = ROOT / "knowledge" / specialty / f"{disease}.yaml"
        by_file.setdefault(yaml_path, []).append(entry)

    for yaml_path, entries in by_file.items():
        if not yaml_path.exists():
            print(f"SKIP {yaml_path}: not found")
            continue
        data = load_yaml(yaml_path)
        added = 0
        for entry in entries:
            if entry_id_exists(data, entry["id"]):
                print(f"  SKIP (exists) {entry['id']}")
                continue
            print(f"  ADD {entry['id']} → {yaml_path.parent.name}/{yaml_path.name}")
            if not dry_run:
                data["entries"].append(entry)
            added += 1
            total += 1
        if added > 0 and not dry_run:
            save_yaml(yaml_path, data)
    print(f"\n{'DRY RUN — ' if dry_run else ''}共添加 {total} 条新 entries")


if __name__ == "__main__":
    main()
