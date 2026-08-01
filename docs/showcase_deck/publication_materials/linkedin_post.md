Built a data pipeline to connect records that were never designed to connect.

Exact matching recovered 63.2% of known links. I taught myself probabilistic entity resolution with Splink because names, dates, and identifiers rarely agree across datasets.

After training one global model and loading it for inference, Splink reached 92.3% recall and 100% precision on a fixed synthetic benchmark—812 true links, or 256 more than exact rules.

That matters for program impact evaluation and research: lots of baseline and follow-up data, messy identities, and rarely enough manpower to connect every entity by hand.

Splink turns that manual matching problem into a scored, reviewable workflow—while leaving uncertain cases for human judgment.

#ProgramEvaluation #ResearchData #DataEngineering #EntityResolution #Splink
