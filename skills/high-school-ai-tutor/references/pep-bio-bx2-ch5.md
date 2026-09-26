学生问人教版《生物学 必修2 遗传与进化》（2019）第五章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 必修2 遗传与进化》（2019）第五章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第五章 基因突变及其他变异"]
    subgraph s1["基因突变和基因重组"]
      kp_gene_mutation["基因突变（概念）"]:::concept
      kp_gene_recombination["基因重组（概念）"]:::concept
    end
    subgraph s2["染色体变异"]
      kp_chromosome_variation["染色体变异（概念）"]:::concept
    end
    subgraph s3["人类遗传病"]
      kp_human_genetic_disease["人类遗传病（概念）"]:::concept
    end
  end
  bx2_ch6["第六章 生物的进化"]:::later
  kp_gene_mutation -->|同章衔接| kp_gene_recombination
  kp_gene_recombination -->|同章衔接| kp_chromosome_variation
  kp_chromosome_variation -->|同章衔接| kp_human_genetic_disease
  kp_gene_mutation -.->|常考组合| kp_dna_replication
  kp_gene_recombination -.->|常考组合| kp_meiosis
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：基因突变、基因重组，还是染色体变异和人类遗传病？
