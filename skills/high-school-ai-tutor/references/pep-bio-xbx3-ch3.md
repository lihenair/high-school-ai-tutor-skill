学生问人教版《生物学 选择性必修3 生物技术与工程》（2019）第三章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 选择性必修3 生物技术与工程》（2019）第三章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第三章 基因工程"]
    subgraph s1["重组 DNA 技术的基本工具"]
      kp_recombinant_dna_tools["重组 DNA 技术的基本工具（概念）"]:::concept
    end
    subgraph s2["基因工程的基本操作程序"]
      kp_gene_engineering_procedure["基因工程的基本操作程序（概念）"]:::concept
    end
    subgraph s3["基因工程的应用"]
      kp_gene_engineering_applications["基因工程的应用（概念）"]:::concept
    end
    subgraph s4["蛋白质工程的原理和应用"]
      kp_protein_engineering["蛋白质工程的原理和应用（概念）"]:::concept
    end
  end
  kp_recombinant_dna_tools -->|同章衔接| kp_gene_engineering_procedure
  kp_gene_engineering_procedure -->|同章衔接| kp_gene_engineering_applications
  kp_gene_engineering_applications -->|同章衔接| kp_protein_engineering
  kp_recombinant_dna_tools -.->|常考组合| kp_dna_structure["DNA 的结构"]:::later
  kp_gene_engineering_procedure -.->|常考组合| kp_secretory_protein["分泌蛋白的合成和运输"]:::later
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：重组 DNA 技术的基本工具、基本操作程序，还是基因工程的应用？
