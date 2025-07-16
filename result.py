import csv
from collections import Counter, defaultdict

# Load votes
filename = "votes.csv"
vote_counts = defaultdict(Counter)

with open(filename, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        for position, candidate in row.items():
            if candidate:
                vote_counts[position][candidate] += 1

# Display results
print("📊 Election Results:\n")
for position in vote_counts:
    print(f"\n🪧 {position}")
    total = sum(vote_counts[position].values())
    for candidate, count in vote_counts[position].most_common():
        print(f"  {candidate}: {count} votes")

    # Find winner(s)
    max_votes = max(vote_counts[position].values())
    winners = [c for c, v in vote_counts[position].items() if v == max_votes]
    if len(winners) == 1:
        print(f"✅ Winner: {winners[0]}")
    else:
        print(f"🤝 Tie between: {', '.join(winners)}")
