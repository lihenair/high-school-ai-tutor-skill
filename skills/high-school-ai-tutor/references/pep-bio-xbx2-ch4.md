学生问人教版《生物学 选择性必修2 生物与环境》（2019）第四章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 选择性必修2 生物与环境》（2019）第四章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第四章 人与环境"]
    subgraph s1["人类活动对生态环境的影响"]
      kp_human_impact["人类活动对生态环境的影响（概念）"]:::concept
    end
    subgraph s2["生物多样性及其保护"]
      kp_biodiversity_protection["生物多样性及其保护（概念）"]:::concept
    end
  end
  kp_human_impact -->|同章衔接| kp_biodiversity_protection
  kp_biodiversity_protection -.->|常考组合| kp_coevolution_biodiversity
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：人类活动对生态环境的影响，还是生物多样性及其保护？
