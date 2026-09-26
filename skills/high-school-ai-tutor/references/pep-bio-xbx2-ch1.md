学生问人教版《生物学 选择性必修2 生物与环境》（2019）第一章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 选择性必修2 生物与环境》（2019）第一章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第一章 种群及其动态"]
    subgraph s1["种群的数量特征"]
      kp_population_features["种群的数量特征（概念）"]:::concept
    end
    subgraph s2["种群数量的变化"]
      kp_population_change["种群数量的变化（概念）"]:::concept
    end
    subgraph s3["影响种群数量变化的因素"]
      kp_population_factors["影响种群数量变化的因素（概念）"]:::concept
    end
  end
  xbx2_ch2["第二章 群落及其演替"]:::later
  kp_population_features -->|同章衔接| kp_population_change
  kp_population_change -->|同章衔接| kp_population_factors
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：种群的数量特征、种群数量的变化，还是影响种群数量变化的因素？
