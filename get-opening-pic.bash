#!/usr/bin/env bash

declare opening_name

if (( $# == 0 ))
then read -r -p "Opening name: " opening_name
else opening_name="$1"
fi

grep "$opening_name:.*" opening-book.txt |
  if
    read
    [[ "$REPLY" =~ :(.*) ]]
  then
    declare moves="${REPLY##*:}"

    echo "go to https://lichess.org/analysis/pgn/${moves// /_},"
    echo "then go to the position editor,"
    echo "and paste the url of the screenshot."
    echo "Press enter when you're done, or q to quit."

  else exit
  fi

cd img/openings
opening_name="${opening_name//[- ,\']/}"

read -r -p "URL: "
if [[ "$REPLY" = q ]]
then exit
elif [[ "$REPLY" =~ color=black ]]
then opening_name+=_black
fi
wget "$REPLY" -q -O "$opening_name.gif"
magick "$opening_name".{gif,png} &&
rm "$opening_name.gif"
