unit module Memchess;

use Chess;
use Chess::PGN;
use Chess::Colors;
use Chess::Position;

use JSON::Fast;

constant %openings = from-json slurp "lines.json";

my %overall-cache;
for <white black> -> $color {
	say "$color";
	for %openings{$color}.pairs {
		say join ' ', .key.match: /<Chess::PGN::SAN><Chess::PGN::annotation>?/, :g;
		for .value.list -> $line {
			my %local-cache;
			#my Chess::Position $pos .= new;
			say "\t" ~ join ' ', $line.match: /<Chess::PGN::SAN><Chess::PGN::annotation>?/, :g;
		}
	}
}

=finish
next unless /^e4/;
state %cache;
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
