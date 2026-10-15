"""Fix the NameError in propose_only."""
path = r"C:\JARVIS 2.0\jarvis\agent.py"
src = open(path, encoding="utf-8").read()
src = src.replace(
    '_log(f"  saved {len(targets)} pending proposal(s)")',
    '_log(f"  saved {len(conflicts)} pending proposal(s)")'
)
open(path, "w", encoding="utf-8").write(src)
print("fixed propose_only NameError")
