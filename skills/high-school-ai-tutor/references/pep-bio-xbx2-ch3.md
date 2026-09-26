学生问人教版《生物学 选择性必修2 生物与环境》（2019）第三章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 选择性必修2 生物与环境》（2019）第三章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第三章 生态系统及其稳定性"]
    subgraph s1["生态系统的结构"]
      kp_ecosystem_structure["生态系统的结构（概念）"]:::concept
    end
    subgraph s2["生态系统的能量流动"]
      kp_energy_flow["生态系统的能量流动（概念）"]:::concept
    end
    subgraph s3["生态系统的物质循环"]
      kp_material_cycle["生态系统的物质循环（概念）"]:::concept
    end
    subgraph s4["生态系统的信息传递"]
      kp_information_transfer["生态系统的信息传递（概念）"]:::concept
    end
    subgraph s5["生态系统的稳定性"]
      kp_ecosystem_stability["生态系统的稳定性（概念）"]:::concept
    end
  end
  kp_ecosystem_structure -->|同章衔接| kp_energy_flow
  kp_energy_flow -->|同章衔接| kp_material_cycle
  kp_material_cycle -->|同章衔接| kp_information_transfer
  kp_information_transfer -->|同章衔接| kp_ecosystem_stability
  kp_energy_flow -.->|常考组合| kp_photosynthesis_principle
  kp_ecosystem_stability -.->|常考组合| kp_homeostasis
  kp_energy_flow -.->|常考组合| kp_aerobic_respiration
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：生态系统的结构、能量流动，还是物质循环和信息传递？
