#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_dataset() -> tuple[list[dict], list[dict], dict[str, list[str]], dict[str, list[str]], list[dict], list[dict], dict]:
    node_types = [
        {
            "id": "skill",
            "layer": "evidence",
            "default_aggregator": "source",
            "description": "技能或工具证据，直接由用户输入或解析得到。",
        },
        {
            "id": "knowledge",
            "layer": "evidence",
            "default_aggregator": "source",
            "description": "课程、理论基础或通用知识证据。",
        },
        {
            "id": "project",
            "layer": "evidence",
            "default_aggregator": "source",
            "description": "项目经历、实践场景或工作方式证据。",
        },
        {
            "id": "interest",
            "layer": "evidence",
            "default_aggregator": "source",
            "description": "兴趣偏好、工作倾向或主观选择。",
        },
        {
            "id": "constraint",
            "layer": "evidence",
            "default_aggregator": "source",
            "description": "明确短板或负向偏好，用于抑制相关方向。",
        },
        {
            "id": "soft_skill",
            "layer": "evidence",
            "default_aggregator": "source",
            "description": "沟通、协作、文档等软技能证据。",
        },
        {
            "id": "ability_unit",
            "layer": "ability",
            "default_aggregator": "weighted_sum_capped",
            "description": "由原子证据聚合得到的基础能力单元。",
        },
        {
            "id": "compound_capability",
            "layer": "composite",
            "default_aggregator": "soft_and",
            "description": "由多个能力单元共同组成的复合能力。",
        },
        {
            "id": "career_direction",
            "layer": "direction",
            "default_aggregator": "penalty_gate",
            "description": "岗位方向或能力簇，连接复合能力与具体职业。",
        },
        {
            "id": "career_role",
            "layer": "role",
            "default_aggregator": "hard_gate",
            "description": "最终推荐的具体职业节点。",
        },
    ]

    edge_types = [
        {
            "id": "supports",
            "sign": "positive",
            "description": "常规正向支持，边权表示对目标节点的贡献力度。",
            "explainable": True,
        },
        {
            "id": "requires",
            "sign": "positive",
            "description": "关键前置关系，会触发门槛或惩罚机制。",
            "explainable": True,
        },
        {
            "id": "prefers",
            "sign": "positive",
            "description": "兴趣或偏好的软加成关系，不单独构成硬门槛。",
            "explainable": True,
        },
        {
            "id": "inhibits",
            "sign": "negative",
            "description": "抑制关系，表示明显短板或负向偏好会压低目标节点。",
            "explainable": True,
        },
        {
            "id": "evidences",
            "sign": "positive",
            "description": "项目、课程等实践性证据，为目标节点提供额外可信度。",
            "explainable": True,
        },
    ]

    nodes: list[dict] = []
    edges: list[dict] = []
    aliases: dict[str, list[str]] = {}

    def add_node(
        node_id: str,
        name: str,
        layer: str,
        node_type: str,
        aggregator: str,
        description: str,
        params: dict | None = None,
        node_aliases: list[str] | None = None,
    ) -> None:
        nodes.append(
            {
                "id": node_id,
                "name": name,
                "layer": layer,
                "node_type": node_type,
                "aggregator": aggregator,
                "description": description,
                "params": params or {},
            }
        )
        if node_aliases:
            aliases[node_id] = sorted({name.lower(), *[alias.lower() for alias in node_aliases]})

    def add_edge(
        source: str,
        target: str,
        relation: str,
        weight: float,
        note: str,
    ) -> None:
        edges.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "weight": weight,
                "note": note,
            }
        )

    skill_specs = [
        ("skill_python", "Python", ["python", "py"]),
        ("skill_java", "Java", ["java"]),
        ("skill_cpp", "C++", ["c++", "cpp"]),
        ("skill_c", "C", ["c language", "c语言"]),
        ("skill_javascript", "JavaScript", ["javascript", "js"]),
        ("skill_typescript", "TypeScript", ["typescript", "ts"]),
        ("skill_golang", "Go", ["go", "golang"]),
        ("skill_rust", "Rust", ["rust"]),
        ("skill_sql", "SQL", ["sql"]),
        ("skill_bash", "Bash", ["bash", "shell", "shell script"]),
        ("tool_flask", "Flask", ["flask"]),
        ("tool_django", "Django", ["django"]),
        ("tool_fastapi", "FastAPI", ["fastapi"]),
        ("tool_spring_boot", "Spring Boot", ["spring", "spring boot"]),
        ("tool_react", "React", ["react"]),
        ("tool_vue", "Vue", ["vue", "vue.js"]),
        ("tool_nodejs", "Node.js", ["node", "nodejs", "node.js"]),
        ("tool_linux", "Linux", ["linux"]),
        ("tool_docker", "Docker", ["docker"]),
        ("tool_kubernetes", "Kubernetes", ["k8s", "kubernetes"]),
        ("tool_git", "Git", ["git"]),
        ("tool_mysql", "MySQL", ["mysql"]),
        ("tool_postgresql", "PostgreSQL", ["postgresql", "postgres"]),
        ("tool_redis", "Redis", ["redis"]),
        ("tool_mongodb", "MongoDB", ["mongodb", "mongo"]),
        ("tool_pandas", "Pandas", ["pandas"]),
        ("tool_numpy", "NumPy", ["numpy"]),
        ("tool_spark", "Spark", ["spark", "apache spark"]),
        ("tool_hadoop", "Hadoop", ["hadoop"]),
        ("tool_kafka", "Kafka", ["kafka"]),
        ("tool_airflow", "Airflow", ["airflow"]),
        ("tool_pytorch", "PyTorch", ["pytorch", "torch"]),
        ("tool_tensorflow", "TensorFlow", ["tensorflow", "tf"]),
        ("tool_scikit_learn", "Scikit-learn", ["sklearn", "scikit-learn"]),
        ("tool_selenium", "Selenium", ["selenium"]),
        ("tool_pytest", "Pytest", ["pytest"]),
        ("tool_wireshark", "Wireshark", ["wireshark"]),
        ("tool_nmap", "Nmap", ["nmap"]),
        ("tool_burp_suite", "Burp Suite", ["burp", "burp suite"]),
        ("tool_aws", "AWS", ["aws"]),
        ("tool_aliyun", "阿里云", ["aliyun", "阿里云"]),
    ]

    knowledge_specs = [
        ("knowledge_data_structures", "数据结构", ["data structures", "数据结构"]),
        ("knowledge_algorithms", "算法", ["algorithms", "算法"]),
        ("knowledge_oop", "面向对象", ["oop", "面向对象"]),
        ("knowledge_database_theory", "数据库原理", ["database theory", "数据库原理"]),
        ("knowledge_operating_systems", "操作系统", ["os", "操作系统"]),
        ("knowledge_networks", "计算机网络", ["networking", "computer networks", "计算机网络"]),
        ("knowledge_statistics", "统计基础", ["statistics", "统计学"]),
        ("knowledge_linear_algebra", "线性代数", ["linear algebra", "线性代数"]),
        ("knowledge_probability", "概率论", ["probability", "概率论"]),
        ("knowledge_system_design", "系统设计", ["system design", "架构设计", "系统设计"]),
        ("knowledge_math_foundation", "数学基础", ["math", "数学", "数学基础"]),
    ]

    project_specs = [
        ("project_backend_api", "后端接口项目", ["backend api", "后端接口", "api项目"]),
        ("project_microservice", "微服务项目", ["microservice", "微服务"]),
        ("project_web_ui", "Web 前端项目", ["web ui", "前端项目", "网页项目"]),
        ("project_data_pipeline", "数据管道项目", ["data pipeline", "数据管道"]),
        ("project_dashboard", "分析看板项目", ["dashboard", "数据看板", "可视化项目"]),
        ("project_model_training", "模型训练项目", ["model training", "模型训练"]),
        ("project_ml_deployment", "模型部署项目", ["ml deployment", "模型部署"]),
        ("project_test_automation", "测试自动化项目", ["test automation", "测试自动化"]),
        ("project_devops_automation", "运维自动化项目", ["devops automation", "运维自动化"]),
        ("project_security_ctf", "安全实战项目", ["ctf", "渗透", "安全项目"]),
    ]

    interest_specs = [
        ("interest_backend", "偏好后端", ["后端", "backend", "后端接口"]),
        ("interest_frontend", "偏好前端", ["前端", "frontend", "界面"]),
        ("interest_data", "偏好数据", ["数据方向", "数据工程", "数据分析", "data"]),
        ("interest_ml", "偏好机器学习", ["机器学习", "ml", "ai", "算法方向"]),
        ("interest_devops", "偏好运维平台", ["运维", "devops", "平台工程"]),
        ("interest_security", "偏好安全", ["安全", "security"]),
        ("interest_stable_delivery", "偏好稳定交付", ["稳定交付", "质量保障", "可靠性"]),
        ("interest_visualization", "偏好可视化表达", ["可视化", "图表", "dashboard"]),
    ]

    soft_specs = [
        ("soft_communication", "沟通表达", ["communication", "沟通"]),
        ("soft_teamwork", "团队协作", ["teamwork", "协作"]),
        ("soft_self_learning", "自主学习", ["自学", "self learning", "自驱"]),
        ("soft_documentation", "文档习惯", ["documentation", "文档"]),
    ]

    constraint_specs = [
        ("constraint_dislike_math_theory", "不喜欢高数学理论", ["不喜欢数学", "数学薄弱", "怕数学", "不太擅长数学"]),
        ("constraint_dislike_oncall", "不喜欢值班运维", ["不想值班", "不喜欢运维值班", "抗拒 oncall", "不喜欢 oncall"]),
        ("constraint_dislike_ui_polish", "不喜欢界面打磨", ["不喜欢前端细节", "不喜欢界面", "不喜欢 ui", "不爱做样式"]),
    ]

    for node_id, name, node_aliases in skill_specs:
        add_node(node_id, name, "evidence", "skill", "source", f"{name} 相关技能或工具证据。", node_aliases=node_aliases)
    for node_id, name, node_aliases in knowledge_specs:
        add_node(node_id, name, "evidence", "knowledge", "source", f"{name} 相关理论基础。", node_aliases=node_aliases)
    for node_id, name, node_aliases in project_specs:
        add_node(node_id, name, "evidence", "project", "source", f"{name} 实践经历。", node_aliases=node_aliases)
    for node_id, name, node_aliases in interest_specs:
        add_node(node_id, name, "evidence", "interest", "source", f"{name} 偏好证据。", node_aliases=node_aliases)
    for node_id, name, node_aliases in soft_specs:
        add_node(node_id, name, "evidence", "soft_skill", "source", f"{name} 软技能证据。", node_aliases=node_aliases)
    for node_id, name, node_aliases in constraint_specs:
        add_node(node_id, name, "evidence", "constraint", "source", f"{name}，会抑制部分职业方向。", node_aliases=node_aliases)

    ability_specs = [
        ("ability_programming_fundamentals", "编程基础", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_database_practice", "数据库实践", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_backend_basics", "后端基础", "weighted_sum_capped", {"cap": 1.0, "required_threshold": 0.12, "required_floor": 0.55}),
        ("ability_python_backend_stack", "Python 后端栈", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_java_backend_stack", "Java 后端栈", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_frontend_basics", "前端基础", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_ui_delivery", "界面交付能力", "max_pool", {"cap": 1.0}),
        ("ability_data_processing", "数据处理能力", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_data_modeling", "数据建模能力", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_ml_foundations", "机器学习基础", "weighted_sum_capped", {"cap": 1.0, "required_threshold": 0.14, "required_floor": 0.35}),
        ("ability_model_training", "模型训练能力", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_devops_basics", "运维开发基础", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_cloud_native", "云原生基础", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_test_automation", "测试自动化能力", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_security_basics", "安全分析基础", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_network_analysis", "网络分析能力", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_system_design", "系统设计能力", "weighted_sum_capped", {"cap": 1.0}),
        ("ability_engineering_collaboration", "工程协作能力", "weighted_sum_capped", {"cap": 1.0}),
    ]

    composite_specs = [
        ("cap_backend_engineering", "后端工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_python_backend_engineering", "Python 后端工程能力", {"min_support_count": 2, "required_threshold": 0.06}),
        ("cap_java_backend_engineering", "Java 后端工程能力", {"min_support_count": 2, "required_threshold": 0.06}),
        ("cap_frontend_engineering", "前端工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_fullstack_engineering", "全栈工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_data_engineering", "数据工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_data_analysis", "数据分析能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_ml_engineering", "机器学习工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_devops_engineering", "DevOps 工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_qa_engineering", "测试开发能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_security_engineering", "安全工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
        ("cap_platform_engineering", "平台工程能力", {"min_support_count": 3, "required_threshold": 0.08}),
    ]

    direction_specs = [
        ("dir_web_backend", "Web 后端方向"),
        ("dir_frontend", "前端方向"),
        ("dir_fullstack", "全栈方向"),
        ("dir_data", "数据方向"),
        ("dir_machine_learning", "机器学习方向"),
        ("dir_devops", "运维平台方向"),
        ("dir_quality_assurance", "测试开发方向"),
        ("dir_security", "安全方向"),
        ("dir_platform", "平台工程方向"),
    ]

    role_specs = [
        ("role_backend_engineer", "后端开发工程师"),
        ("role_python_backend_engineer", "Python 后端工程师"),
        ("role_java_backend_engineer", "Java 后端工程师"),
        ("role_frontend_engineer", "前端工程师"),
        ("role_fullstack_engineer", "全栈工程师"),
        ("role_data_engineer", "数据工程师"),
        ("role_data_analyst", "数据分析师"),
        ("role_ml_engineer", "机器学习工程师"),
        ("role_devops_engineer", "DevOps 工程师"),
        ("role_test_development_engineer", "测试开发工程师"),
        ("role_security_engineer", "安全工程师"),
        ("role_platform_engineer", "平台工程师"),
    ]

    for node_id, name, aggregator, params in ability_specs:
        add_node(node_id, name, "ability", "ability_unit", aggregator, f"{name}，由多种证据聚合而成。", params=params)
    for node_id, name, params in composite_specs:
        add_node(node_id, name, "composite", "compound_capability", "soft_and", f"{name}，用于连接基础能力与职业方向。", params=params)
    for node_id, name in direction_specs:
        add_node(
            node_id,
            name,
            "direction",
            "career_direction",
            "penalty_gate",
            f"{name}，承接复合能力并汇入具体岗位。",
            params={"cap": 1.0, "required_threshold": 0.03, "penalty_floor": 0.45},
        )
    for node_id, name in role_specs:
        add_node(
            node_id,
            name,
            "role",
            "career_role",
            "hard_gate",
            f"{name}，最终推荐岗位节点。",
            params={"cap": 1.0, "required_threshold": 0.025},
        )

    def link_many(sources: list[str], target: str, relation: str, weight: float, note: str) -> None:
        for source in sources:
            add_edge(source, target, relation, weight, note)

    link_many(
        [
            "skill_python",
            "skill_java",
            "skill_cpp",
            "skill_c",
            "skill_javascript",
            "skill_typescript",
            "skill_golang",
            "skill_rust",
            "skill_bash",
            "tool_git",
            "knowledge_oop",
        ],
        "ability_programming_fundamentals",
        "supports",
        0.18,
        "主流编程语言和版本控制共同支撑编程基础。",
    )
    link_many(
        ["knowledge_data_structures", "knowledge_algorithms"],
        "ability_programming_fundamentals",
        "requires",
        0.22,
        "数据结构与算法是编程基础的重要前置。",
    )

    link_many(
        ["skill_sql", "tool_mysql", "tool_postgresql", "tool_mongodb", "tool_redis"],
        "ability_database_practice",
        "supports",
        0.22,
        "数据库及缓存工具提升数据库实践能力。",
    )
    add_edge("knowledge_database_theory", "ability_database_practice", "requires", 0.25, "数据库原理支撑数据库实践。")

    link_many(
        ["tool_flask", "tool_django", "tool_fastapi", "tool_spring_boot", "tool_nodejs", "project_backend_api"],
        "ability_backend_basics",
        "supports",
        0.18,
        "常见服务端框架和接口项目支撑后端基础。",
    )
    link_many(
        ["ability_programming_fundamentals", "ability_database_practice"],
        "ability_backend_basics",
        "requires",
        0.3,
        "后端基础依赖编程和数据库能力。",
    )
    add_edge("tool_linux", "ability_backend_basics", "supports", 0.14, "Linux 使用经验能增强后端基础。")

    link_many(
        ["skill_python", "tool_flask", "tool_django", "tool_fastapi", "tool_redis"],
        "ability_python_backend_stack",
        "supports",
        0.2,
        "Python 及相关框架形成 Python 后端技术栈。",
    )
    add_edge("ability_backend_basics", "ability_python_backend_stack", "requires", 0.25, "Python 后端栈建立在后端基础上。")

    link_many(
        ["skill_java", "tool_spring_boot", "tool_redis", "tool_mysql"],
        "ability_java_backend_stack",
        "supports",
        0.22,
        "Java 与 Spring Boot 形成 Java 后端技术栈。",
    )
    add_edge("ability_backend_basics", "ability_java_backend_stack", "requires", 0.25, "Java 后端栈建立在后端基础上。")

    link_many(
        ["skill_javascript", "skill_typescript", "tool_react", "tool_vue", "tool_nodejs", "project_web_ui"],
        "ability_frontend_basics",
        "supports",
        0.18,
        "前端语言、框架和项目实践构成前端基础。",
    )
    add_edge("ability_programming_fundamentals", "ability_frontend_basics", "requires", 0.22, "前端基础依赖通用编程基础。")

    link_many(
        ["tool_react", "tool_vue", "project_web_ui", "interest_visualization", "soft_documentation"],
        "ability_ui_delivery",
        "supports",
        0.22,
        "框架实践与可视化偏好支撑界面交付能力。",
    )
    add_edge("constraint_dislike_ui_polish", "ability_ui_delivery", "inhibits", 0.35, "不喜欢界面打磨会压低界面交付能力。")

    link_many(
        ["skill_python", "skill_sql", "tool_pandas", "tool_numpy", "tool_spark", "tool_hadoop", "project_data_pipeline"],
        "ability_data_processing",
        "supports",
        0.17,
        "脚本、SQL 和大数据工具共同构成数据处理能力。",
    )
    add_edge("ability_programming_fundamentals", "ability_data_processing", "requires", 0.22, "数据处理依赖编程基础。")

    link_many(
        ["skill_sql", "knowledge_database_theory", "knowledge_statistics", "project_dashboard"],
        "ability_data_modeling",
        "supports",
        0.22,
        "数据库与统计基础支撑数据建模能力。",
    )
    add_edge("ability_database_practice", "ability_data_modeling", "requires", 0.25, "数据建模建立在数据库实践上。")

    link_many(
        [
            "skill_python",
            "tool_numpy",
            "tool_scikit_learn",
            "knowledge_statistics",
            "knowledge_linear_algebra",
            "knowledge_probability",
            "knowledge_algorithms",
        ],
        "ability_ml_foundations",
        "supports",
        0.16,
        "Python、统计和数学知识共同组成机器学习基础。",
    )
    add_edge("knowledge_math_foundation", "ability_ml_foundations", "requires", 0.3, "机器学习基础要求数学基础。")
    add_edge("constraint_dislike_math_theory", "ability_ml_foundations", "inhibits", 0.28, "不喜欢数学理论会压低机器学习基础。")

    link_many(
        ["tool_pytorch", "tool_tensorflow", "project_model_training", "project_ml_deployment"],
        "ability_model_training",
        "supports",
        0.22,
        "训练框架与项目实践支撑模型训练能力。",
    )
    add_edge("ability_ml_foundations", "ability_model_training", "requires", 0.28, "模型训练能力建立在机器学习基础上。")

    link_many(
        ["tool_linux", "skill_bash", "tool_docker", "tool_git", "project_devops_automation", "tool_aws", "tool_aliyun"],
        "ability_devops_basics",
        "supports",
        0.17,
        "Linux、脚本、容器和自动化项目支撑运维开发基础。",
    )
    add_edge("constraint_dislike_oncall", "ability_devops_basics", "inhibits", 0.22, "抗拒 on-call 会压低运维开发基础。")

    link_many(
        ["tool_docker", "tool_kubernetes", "tool_aws", "tool_aliyun", "tool_kafka", "tool_airflow", "tool_linux"],
        "ability_cloud_native",
        "supports",
        0.16,
        "容器、编排和云平台经验构成云原生基础。",
    )
    add_edge("ability_devops_basics", "ability_cloud_native", "requires", 0.22, "云原生能力建立在运维开发基础上。")

    link_many(
        ["tool_selenium", "tool_pytest", "project_test_automation", "skill_python", "skill_javascript"],
        "ability_test_automation",
        "supports",
        0.2,
        "测试工具与脚本能力支撑测试自动化能力。",
    )
    add_edge("ability_programming_fundamentals", "ability_test_automation", "requires", 0.2, "测试自动化依赖编程基础。")

    link_many(
        ["tool_linux", "knowledge_networks", "tool_wireshark", "tool_nmap", "tool_burp_suite", "project_security_ctf"],
        "ability_security_basics",
        "supports",
        0.18,
        "网络与安全工具实践构成安全分析基础。",
    )
    add_edge("ability_programming_fundamentals", "ability_security_basics", "requires", 0.18, "安全分析基础依赖编程理解。")

    link_many(
        ["knowledge_networks", "tool_wireshark", "tool_nmap", "tool_linux"],
        "ability_network_analysis",
        "supports",
        0.24,
        "网络理论与抓包扫描工具支撑网络分析能力。",
    )
    add_edge("ability_security_basics", "ability_network_analysis", "requires", 0.2, "网络分析常与安全基础联动。")

    link_many(
        ["knowledge_system_design", "knowledge_operating_systems", "knowledge_networks", "tool_redis", "tool_kafka", "project_microservice"],
        "ability_system_design",
        "supports",
        0.16,
        "系统设计、操作系统、网络和中间件共同构成系统设计能力。",
    )
    add_edge("ability_backend_basics", "ability_system_design", "requires", 0.2, "系统设计能力建立在后端基础上。")

    link_many(
        ["soft_communication", "soft_teamwork", "soft_self_learning", "soft_documentation", "tool_git"],
        "ability_engineering_collaboration",
        "supports",
        0.18,
        "沟通、协作、文档和 Git 协作形成工程协作能力。",
    )
    link_many(
        ["project_backend_api", "project_web_ui", "project_data_pipeline", "project_test_automation", "project_devops_automation"],
        "ability_engineering_collaboration",
        "evidences",
        0.12,
        "项目经历为工程协作提供额外证据。",
    )

    link_many(
        ["ability_backend_basics", "ability_database_practice", "ability_system_design", "ability_engineering_collaboration"],
        "cap_backend_engineering",
        "supports",
        0.22,
        "后端工程能力来自基础后端、数据库、系统设计与协作能力。",
    )
    add_edge("project_backend_api", "cap_backend_engineering", "evidences", 0.2, "后端接口项目是后端工程能力的直接证据。")
    add_edge("interest_backend", "cap_backend_engineering", "prefers", 0.18, "偏好后端会提升后端工程方向。")

    link_many(
        ["ability_python_backend_stack", "cap_backend_engineering"],
        "cap_python_backend_engineering",
        "supports",
        0.28,
        "Python 后端工程能力由 Python 技术栈与通用后端工程能力共同组成。",
    )
    add_edge("ability_python_backend_stack", "cap_python_backend_engineering", "requires", 0.32, "Python 栈是该能力的关键前置。")

    link_many(
        ["ability_java_backend_stack", "cap_backend_engineering"],
        "cap_java_backend_engineering",
        "supports",
        0.28,
        "Java 后端工程能力由 Java 技术栈与通用后端工程能力共同组成。",
    )
    add_edge("ability_java_backend_stack", "cap_java_backend_engineering", "requires", 0.32, "Java 栈是该能力的关键前置。")

    link_many(
        ["ability_frontend_basics", "ability_ui_delivery", "ability_engineering_collaboration"],
        "cap_frontend_engineering",
        "supports",
        0.24,
        "前端工程能力依赖前端基础、界面交付与协作能力。",
    )
    add_edge("interest_frontend", "cap_frontend_engineering", "prefers", 0.2, "偏好前端会提升前端工程能力。")
    add_edge("constraint_dislike_ui_polish", "cap_frontend_engineering", "inhibits", 0.28, "不喜欢界面打磨会压低前端工程能力。")

    link_many(
        ["cap_backend_engineering", "cap_frontend_engineering", "ability_system_design"],
        "cap_fullstack_engineering",
        "supports",
        0.24,
        "全栈工程能力需要前后端与系统设计共同支撑。",
    )
    link_many(["interest_backend", "interest_frontend"], "cap_fullstack_engineering", "prefers", 0.12, "同时偏好前后端会增强全栈倾向。")

    link_many(
        ["ability_data_processing", "ability_database_practice", "ability_cloud_native", "ability_engineering_collaboration"],
        "cap_data_engineering",
        "supports",
        0.2,
        "数据工程能力依赖数据处理、数据库、云原生与协作能力。",
    )
    add_edge("project_data_pipeline", "cap_data_engineering", "evidences", 0.24, "数据管道项目是数据工程能力的核心证据。")
    add_edge("interest_data", "cap_data_engineering", "prefers", 0.18, "偏好数据会增强数据工程方向。")

    link_many(
        ["ability_data_processing", "ability_data_modeling", "ability_engineering_collaboration"],
        "cap_data_analysis",
        "supports",
        0.24,
        "数据分析能力依赖数据处理、建模和协作表达。",
    )
    add_edge("project_dashboard", "cap_data_analysis", "evidences", 0.24, "分析看板项目是数据分析能力的重要证据。")
    link_many(["interest_data", "interest_visualization"], "cap_data_analysis", "prefers", 0.14, "偏好数据和可视化会增强分析方向。")

    link_many(
        ["ability_ml_foundations", "ability_model_training", "ability_data_processing", "ability_cloud_native"],
        "cap_ml_engineering",
        "supports",
        0.19,
        "机器学习工程能力需要基础、训练、数据和部署能力协同。",
    )
    add_edge("ability_ml_foundations", "cap_ml_engineering", "requires", 0.3, "机器学习基础是该能力的硬前置。")
    add_edge("interest_ml", "cap_ml_engineering", "prefers", 0.18, "偏好机器学习会增强该方向。")
    add_edge("constraint_dislike_math_theory", "cap_ml_engineering", "inhibits", 0.3, "不喜欢数学理论会抑制机器学习方向。")

    link_many(
        ["ability_devops_basics", "ability_cloud_native", "ability_system_design", "ability_engineering_collaboration"],
        "cap_devops_engineering",
        "supports",
        0.2,
        "DevOps 能力需要运维基础、云原生、系统设计和协作能力。",
    )
    link_many(["interest_devops", "interest_stable_delivery"], "cap_devops_engineering", "prefers", 0.14, "偏好运维平台和稳定交付会增强 DevOps 能力。")
    add_edge("constraint_dislike_oncall", "cap_devops_engineering", "inhibits", 0.3, "抗拒值班会抑制 DevOps 能力。")

    link_many(
        ["ability_test_automation", "ability_programming_fundamentals", "ability_engineering_collaboration"],
        "cap_qa_engineering",
        "supports",
        0.24,
        "测试开发能力由测试自动化、编程基础和协作能力共同组成。",
    )
    add_edge("project_test_automation", "cap_qa_engineering", "evidences", 0.24, "测试自动化项目是测试开发能力的直接证据。")
    add_edge("interest_stable_delivery", "cap_qa_engineering", "prefers", 0.16, "偏好稳定交付会增强测试开发方向。")

    link_many(
        ["ability_security_basics", "ability_network_analysis", "ability_programming_fundamentals"],
        "cap_security_engineering",
        "supports",
        0.24,
        "安全工程能力由安全基础、网络分析和编程能力共同组成。",
    )
    add_edge("project_security_ctf", "cap_security_engineering", "evidences", 0.26, "安全实战项目是安全方向的重要证据。")
    add_edge("interest_security", "cap_security_engineering", "prefers", 0.18, "偏好安全会增强安全工程能力。")

    link_many(
        ["cap_backend_engineering", "cap_devops_engineering", "ability_cloud_native", "ability_system_design"],
        "cap_platform_engineering",
        "supports",
        0.2,
        "平台工程能力需要后端、运维、云原生和系统设计协同。",
    )
    add_edge("interest_stable_delivery", "cap_platform_engineering", "prefers", 0.16, "偏好稳定交付会增强平台工程方向。")

    link_many(
        ["cap_backend_engineering", "cap_python_backend_engineering", "cap_java_backend_engineering"],
        "dir_web_backend",
        "supports",
        0.22,
        "多种后端能力簇共同支撑 Web 后端方向。",
    )
    add_edge("cap_backend_engineering", "dir_web_backend", "requires", 0.3, "后端工程能力是 Web 后端方向的关键前置。")
    add_edge("interest_backend", "dir_web_backend", "prefers", 0.16, "偏好后端会增强 Web 后端方向。")

    add_edge("cap_frontend_engineering", "dir_frontend", "supports", 0.3, "前端工程能力直接支撑前端方向。")
    add_edge("cap_frontend_engineering", "dir_frontend", "requires", 0.32, "前端工程能力是前端方向的关键前置。")
    add_edge("interest_frontend", "dir_frontend", "prefers", 0.18, "偏好前端会增强前端方向。")
    add_edge("constraint_dislike_ui_polish", "dir_frontend", "inhibits", 0.28, "不喜欢界面打磨会抑制前端方向。")

    link_many(
        ["cap_fullstack_engineering", "cap_backend_engineering", "cap_frontend_engineering"],
        "dir_fullstack",
        "supports",
        0.22,
        "全栈方向需要前后端能力共同支撑。",
    )
    add_edge("cap_fullstack_engineering", "dir_fullstack", "requires", 0.3, "全栈工程能力是全栈方向的关键前置。")

    link_many(
        ["cap_data_engineering", "cap_data_analysis"],
        "dir_data",
        "supports",
        0.28,
        "数据工程与数据分析共同支撑数据方向。",
    )
    add_edge("cap_data_engineering", "dir_data", "requires", 0.18, "数据工程能力是数据方向的重要前置。")
    add_edge("interest_data", "dir_data", "prefers", 0.16, "偏好数据会增强数据方向。")

    link_many(
        ["cap_ml_engineering", "ability_ml_foundations", "ability_model_training"],
        "dir_machine_learning",
        "supports",
        0.22,
        "机器学习方向由工程能力、基础与训练能力共同支撑。",
    )
    add_edge("cap_ml_engineering", "dir_machine_learning", "requires", 0.32, "机器学习工程能力是机器学习方向的关键前置。")
    add_edge("interest_ml", "dir_machine_learning", "prefers", 0.18, "偏好机器学习会增强该方向。")
    add_edge("constraint_dislike_math_theory", "dir_machine_learning", "inhibits", 0.3, "不喜欢数学理论会抑制机器学习方向。")

    link_many(
        ["cap_devops_engineering", "cap_platform_engineering"],
        "dir_devops",
        "supports",
        0.26,
        "DevOps 与平台工程能力共同支撑运维平台方向。",
    )
    add_edge("cap_devops_engineering", "dir_devops", "requires", 0.3, "DevOps 工程能力是运维平台方向的关键前置。")
    add_edge("interest_devops", "dir_devops", "prefers", 0.18, "偏好运维平台会增强该方向。")
    add_edge("constraint_dislike_oncall", "dir_devops", "inhibits", 0.28, "抗拒值班会抑制运维平台方向。")

    add_edge("cap_qa_engineering", "dir_quality_assurance", "supports", 0.3, "测试开发能力直接支撑测试开发方向。")
    add_edge("cap_qa_engineering", "dir_quality_assurance", "requires", 0.3, "测试开发能力是测试开发方向的关键前置。")
    add_edge("interest_stable_delivery", "dir_quality_assurance", "prefers", 0.18, "偏好稳定交付会增强测试开发方向。")

    add_edge("cap_security_engineering", "dir_security", "supports", 0.3, "安全工程能力直接支撑安全方向。")
    add_edge("cap_security_engineering", "dir_security", "requires", 0.32, "安全工程能力是安全方向的关键前置。")
    add_edge("interest_security", "dir_security", "prefers", 0.18, "偏好安全会增强安全方向。")

    link_many(
        ["cap_platform_engineering", "cap_devops_engineering", "cap_backend_engineering"],
        "dir_platform",
        "supports",
        0.22,
        "平台工程方向需要平台、DevOps 与后端能力协同。",
    )
    add_edge("cap_platform_engineering", "dir_platform", "requires", 0.3, "平台工程能力是平台方向的关键前置。")
    add_edge("interest_stable_delivery", "dir_platform", "prefers", 0.16, "偏好稳定交付会增强平台方向。")

    link_many(["dir_web_backend", "cap_backend_engineering"], "role_backend_engineer", "supports", 0.26, "后端方向与后端工程能力共同支撑后端工程师岗位。")
    add_edge("cap_backend_engineering", "role_backend_engineer", "requires", 0.32, "后端工程能力是后端工程师的关键前置。")
    add_edge("interest_backend", "role_backend_engineer", "prefers", 0.16, "偏好后端会增强岗位匹配度。")

    link_many(["dir_web_backend", "cap_python_backend_engineering"], "role_python_backend_engineer", "supports", 0.28, "Python 后端方向与能力共同支撑 Python 后端岗位。")
    add_edge("cap_python_backend_engineering", "role_python_backend_engineer", "requires", 0.34, "Python 后端工程能力是该岗位的关键前置。")

    link_many(["dir_web_backend", "cap_java_backend_engineering"], "role_java_backend_engineer", "supports", 0.28, "Java 后端方向与能力共同支撑 Java 后端岗位。")
    add_edge("cap_java_backend_engineering", "role_java_backend_engineer", "requires", 0.34, "Java 后端工程能力是该岗位的关键前置。")

    link_many(["dir_frontend", "cap_frontend_engineering"], "role_frontend_engineer", "supports", 0.28, "前端方向与前端工程能力共同支撑前端岗位。")
    add_edge("cap_frontend_engineering", "role_frontend_engineer", "requires", 0.34, "前端工程能力是前端岗位的关键前置。")
    add_edge("constraint_dislike_ui_polish", "role_frontend_engineer", "inhibits", 0.34, "不喜欢界面打磨会压低前端岗位。")

    link_many(["dir_fullstack", "cap_fullstack_engineering"], "role_fullstack_engineer", "supports", 0.28, "全栈方向与全栈能力共同支撑全栈岗位。")
    add_edge("cap_fullstack_engineering", "role_fullstack_engineer", "requires", 0.34, "全栈工程能力是全栈岗位的关键前置。")

    link_many(["dir_data", "cap_data_engineering"], "role_data_engineer", "supports", 0.28, "数据方向与数据工程能力共同支撑数据工程师岗位。")
    add_edge("cap_data_engineering", "role_data_engineer", "requires", 0.34, "数据工程能力是数据工程师的关键前置。")
    add_edge("interest_data", "role_data_engineer", "prefers", 0.16, "偏好数据会增强岗位匹配度。")

    link_many(["dir_data", "cap_data_analysis"], "role_data_analyst", "supports", 0.28, "数据方向与数据分析能力共同支撑数据分析师岗位。")
    add_edge("cap_data_analysis", "role_data_analyst", "requires", 0.3, "数据分析能力是数据分析师的关键前置。")
    add_edge("interest_visualization", "role_data_analyst", "prefers", 0.16, "偏好可视化会增强数据分析师匹配度。")

    link_many(["dir_machine_learning", "cap_ml_engineering"], "role_ml_engineer", "supports", 0.28, "机器学习方向与工程能力共同支撑机器学习工程师岗位。")
    add_edge("cap_ml_engineering", "role_ml_engineer", "requires", 0.36, "机器学习工程能力是机器学习岗位的关键前置。")
    add_edge("constraint_dislike_math_theory", "role_ml_engineer", "inhibits", 0.34, "不喜欢数学理论会显著压低机器学习岗位。")

    link_many(["dir_devops", "cap_devops_engineering"], "role_devops_engineer", "supports", 0.28, "运维平台方向与 DevOps 能力共同支撑 DevOps 岗位。")
    add_edge("cap_devops_engineering", "role_devops_engineer", "requires", 0.34, "DevOps 工程能力是 DevOps 岗位的关键前置。")
    add_edge("constraint_dislike_oncall", "role_devops_engineer", "inhibits", 0.34, "抗拒值班会显著压低 DevOps 岗位。")

    link_many(["dir_quality_assurance", "cap_qa_engineering"], "role_test_development_engineer", "supports", 0.28, "测试开发方向与测试能力共同支撑测试开发岗位。")
    add_edge("cap_qa_engineering", "role_test_development_engineer", "requires", 0.34, "测试开发能力是测试开发岗位的关键前置。")

    link_many(["dir_security", "cap_security_engineering"], "role_security_engineer", "supports", 0.28, "安全方向与安全能力共同支撑安全岗位。")
    add_edge("cap_security_engineering", "role_security_engineer", "requires", 0.34, "安全工程能力是安全岗位的关键前置。")

    link_many(["dir_platform", "cap_platform_engineering"], "role_platform_engineer", "supports", 0.28, "平台方向与平台能力共同支撑平台工程岗位。")
    add_edge("cap_platform_engineering", "role_platform_engineer", "requires", 0.34, "平台工程能力是平台工程岗位的关键前置。")
    add_edge("interest_stable_delivery", "role_platform_engineer", "prefers", 0.16, "偏好稳定交付会增强平台工程岗位匹配度。")

    preference_patterns = {
        "strong_positive": ["精通", "熟练", "擅长", "扎实"],
        "medium_positive": ["熟悉", "做过", "写过", "使用过", "实践过", "经验"],
        "light_positive": ["会", "了解", "接触过", "用过"],
        "weak_positive": ["一点", "入门", "略懂", "会一点"],
        "negative": ["不擅长", "不太擅长", "薄弱", "不会", "不喜欢", "讨厌", "抗拒", "不想", "不想做", "不想写", "不愿", "没兴趣"],
        "preference": ["喜欢", "更喜欢", "偏好", "倾向", "想做", "希望做"],
    }

    sample_request = {
        "text": "我熟悉 Python 和 MySQL，做过 Flask 项目，会一点 Linux，不太擅长数学，更喜欢写后端接口。",
        "signals": [
            {"entity": "SQL", "score": 0.72},
            {"entity": "沟通表达", "score": 0.55},
        ],
        "top_k": 5,
    }

    return node_types, edge_types, aliases, preference_patterns, nodes, edges, sample_request


def main() -> None:
    node_types, edge_types, aliases, preference_patterns, nodes, edges, sample_request = build_dataset()

    ontology_dir = ROOT / "data" / "ontology"
    seeds_dir = ROOT / "data" / "seeds"
    dictionaries_dir = ROOT / "data" / "dictionaries"
    demo_dir = ROOT / "data" / "demo"

    for path in [ontology_dir, seeds_dir, dictionaries_dir, demo_dir]:
        ensure_dir(path)

    write_json(ontology_dir / "node_types.json", node_types)
    write_json(ontology_dir / "edge_types.json", edge_types)
    write_json(seeds_dir / "nodes.json", nodes)
    write_json(seeds_dir / "edges.json", edges)
    write_json(dictionaries_dir / "skill_aliases.json", aliases)
    write_json(dictionaries_dir / "preference_patterns.json", preference_patterns)
    write_json(demo_dir / "sample_request.json", sample_request)

    print(f"generated {len(nodes)} nodes and {len(edges)} edges")


if __name__ == "__main__":
    main()
