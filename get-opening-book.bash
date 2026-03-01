for l in a b c d e
do wget -O - -q https://raw.githubusercontent.com/lichess-org/chess-openings/refs/heads/master/$l.tsv
done 
