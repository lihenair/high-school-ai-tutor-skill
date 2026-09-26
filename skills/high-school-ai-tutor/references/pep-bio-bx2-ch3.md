学生问人教版《生物学 必修2 遗传与进化》（2019）第三章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 必修2 遗传与进化》（2019）第三章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第三章 基因的本质"]
    subgraph s1["DNA 是主要的遗传物质"]
      kp_dna_genetic_material["DNA 是主要的遗传物质（概念）"]:::concept
    end
    subgraph s2["DNA 的结构"]
      kp_dna_structure["DNA 的结构（概念）"]:::concept
    end
    subgraph s3["DNA 的复制"]
      kp_dna_replication["DNA 的复制（概念）"]:::concept
    end
    subgraph s4["基因通常是有遗传效应的 DNA 片段"]
      kp_gene_dna_fragment["基因通常是有遗传效应的 DNA 片段（概念）"]:::concept
    end
  end
  bx2_ch4["第四章 基因的表达"]:::later
  kp_dna_genetic_material -->|同章衔接| kp_dna_structure
  kp_dna_structure -->|同章衔接| kp_dna_replication
  kp_dna_replication -->|同章衔接| kp_gene_dna_fragment
  kp_dna_structure -.->|常考组合| kp_nucleic_acids
  kp_dna_replication -.->|常考组合| kp_mitosis
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：DNA 是主要的遗传物质、DNA 的结构，还是 DNA 的复制？
