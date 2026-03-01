use Chess;
use Chess::PGN;
use Chess::Colors;
use Chess::Position;

use JSON::Fast;

my %lines = from-json slurp "candidate-lines.json";

my %zobrist;
my %book;
for |%lines<white> {
	given .match(/^[<Chess::PGN::SAN><Chess::PGN::annotation>?]+$/) -> $/ {

		my @moves = $<Chess::PGN::SAN>.map(*.Str);
		my Chess::Position $position .= new;
		for @moves -> $move {
			my $zobrist = $position.uint.base(36);
			%zobrist{$zobrist} = $position.fen;
			%book{$zobrist}{$move}++ if $position.turn ~~ white;
			try {
				$position = $position * $move;
				CATCH {
					default {
						.say for $move, $position.ascii;
						.throw
					}
				}
			}

		}

	}
		
}

for %book.keys.grep({ %book{$_} > 1 }) {

	say Chess::Position.new(%zobrist{$_}).unicode;

}

=finish
given .match(/^[<Chess::PGN::SAN><Chess::PGN::annotation>?]+$/) -> $/ {
	my @moves = $<Chess::PGN::SAN>.map: *.Str;
	my Chess::Position $position .= new;
	for @moves -> $move {
		my $zobrist = $position.uint.base(36);
		%cache{$zobrist}{$move}++ if $position.turn ~~ white;
		if %cache{$zobrist}.keys > 1 {
			note @moves;
			note $position.fen => %cache{$zobrist}.keys;
		}
		try {
			$position = $position * $move;
			CATCH {
				default {
					.say for $move, $position.ascii;
					.throw
				}
			}
		}
	}
}
