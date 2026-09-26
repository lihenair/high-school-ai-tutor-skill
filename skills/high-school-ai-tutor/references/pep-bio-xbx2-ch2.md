学生问人教版《生物学 选择性必修2 生物与环境》（2019）第二章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 选择性必修2 生物与环境》（2019）第二章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第二章 群落及其演替"]
    subgraph s1["群落的结构"]
      kp_community_structure["群落的结构（概念）"]:::concept
    end
    subgraph s2["群落的主要类型"]
      kp_community_types["群落的主要类型（概念）"]:::concept
    end
    subgraph s3["群落的演替"]
      kp_ecological_succession["群落的演替（概念）"]:::concept
    end
  end
  xbx2_ch3["第三章 生态系统及其稳定性"]:::later
  kp_community_structure -->|同章衔接| kp_community_types
  kp_community_types -->|同章衔接| kp_ecological_succession
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：群落的结构、群落的主要类型，还是群落的演替？
