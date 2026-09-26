学生问人教版《生物学 必修1 分子与细胞》（2019）第四章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 必修1 分子与细胞》（2019）第四章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第四章 细胞的物质输入和输出"]
    subgraph s1["被动运输"]
      kp_osmosis["渗透作用（概念）"]:::concept
      kp_plasmolysis["质壁分离及复原（实验）"]:::experiment
      kp_passive_transport["被动运输（概念）"]:::concept
    end
    subgraph s2["主动运输与胞吞、胞吐"]
      kp_active_transport["主动运输（概念）"]:::concept
      kp_endocytosis_exocytosis["胞吞和胞吐（概念）"]:::concept
    end
  end
  bx1_ch5["第五章 细胞的能量供应和利用"]:::later
  bx1_ch6["第六章 细胞的生命历程"]:::later
  kp_osmosis -->|同章衔接| kp_plasmolysis
  kp_plasmolysis -->|同章衔接| kp_passive_transport
  kp_passive_transport -->|同章衔接| kp_active_transport
  kp_active_transport -->|同章衔接| kp_endocytosis_exocytosis
  kp_cell_membrane_functions -.->|常考组合| kp_passive_transport
  kp_fluid_mosaic -.->|常考组合| kp_endocytosis_exocytosis
  kp_active_transport -.->|常考组合| bx1_ch5
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：渗透作用、被动运输，还是主动运输？
