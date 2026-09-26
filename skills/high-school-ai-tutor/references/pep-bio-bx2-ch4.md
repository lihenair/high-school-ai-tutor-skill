学生问人教版《生物学 必修2 遗传与进化》（2019）第四章的知识图谱时，从「整章图」那一行起原样输出，不要改节点、边和配色。

整章图：人教版《生物学 必修2 遗传与进化》（2019）第四章

```mermaid
flowchart TD
  classDef concept fill:#E8F1FF,stroke:#3B6FB6,color:#1A1A1A
  classDef skill fill:#E7F6EE,stroke:#2E7D4F,color:#1A1A1A
  classDef experiment fill:#FFF4E5,stroke:#C47B17,color:#1A1A1A
  classDef later fill:#F4F4F5,stroke:#71717A,color:#1A1A1A
  subgraph ch["第四章 基因的表达"]
    subgraph s1["基因指导蛋白质的合成"]
      kp_transcription_translation["基因指导蛋白质的合成（概念）"]:::concept
      kp_central_dogma["中心法则（概念）"]:::concept
    end
    subgraph s2["基因表达与性状的关系"]
      kp_gene_expression_trait["基因表达与性状的关系（概念）"]:::concept
      kp_epigenetics["表观遗传（概念）"]:::concept
    end
  end
  bx2_ch5["第五章 基因突变及其他变异"]:::later
  kp_transcription_translation -->|同章衔接| kp_central_dogma
  kp_central_dogma -->|同章衔接| kp_gene_expression_trait
  kp_gene_expression_trait -->|同章衔接| kp_epigenetics
  kp_transcription_translation -.->|常考组合| kp_proteins
  kp_gene_expression_trait -.->|常考组合| kp_cell_differentiation
```

图例：蓝=概念，绿=技能，橙=实验，灰=后续章节。实线=直接前置或同章衔接，虚线=常考组合。

先学哪个节点：基因指导蛋白质的合成、中心法则，还是基因表达与性状的关系？
