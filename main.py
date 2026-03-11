from agent.foldseek_agent import FoldseekAgent


if __name__ == "__main__":
    agent = FoldseekAgent("config/config.yaml")
    hits = agent.search_structure("example.pdb", database="afdb50")
    print(hits)
