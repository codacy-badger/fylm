# -*- coding: future_fstrings -*-
# Copyright 2018 Brandon Shelley. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main file parser for Fylm.

This module takes raw input source paths and cleans/analyzes them
to determine various properties used in the name correction
and TMDb lookup.

    parser: the main class exported by this module.
"""

from __future__ import unicode_literals, print_function
from builtins import *

import os
import re

import fylmlib.config as config
import fylmlib.patterns as patterns
import fylmlib.formatter as formatter
from fylmlib.enums import Media

class parser:
    """Main class for film parser.

    All methods are class methods, thus this class should never be instantiated.
    """
    @classmethod
    def get_title(cls, source_path):
        """Get title from full path of file or folder.

        Use regular expressions to strip, clean, and format a file
        or folder path into a more pleasant film title.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A clean and well-formed film title.
        """

        # Ensure source_path is a str
        source_path = str(source_path)

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        # Determine whether to use the file or its containing folder
        # to determine the title by parsing for year and resolution
        title = folder if cls.get_year(folder) is not None or cls.get_resolution(folder) is not None else file

        # Remove the file extension.
        title = os.path.splitext(title)[0]

        # Strip "tag" prefixes from the title.
        for prefix in config.strip_prefixes:
            if title.lower().startswith(prefix.lower()):
                title = title[len(prefix):]

        # For a title that properly begins with 'The' (which was previously
        # converted to append ', The' instead), we need to put it back to its
        # original state both for lookup validation, and so that we don't
        # end up with multiple ', the' suffixes.
        if re.search(r', the', title, re.I):
            title = f"The {re.sub(r', the', '', title, flags=re.I)}"

        # Use the 'strip_from_title' regular expression to replace unwanted
        # characters in a title with a space.
        title = re.sub(patterns.strip_from_title, ' ', title)
        
        # If the title contains a known edition, strip it from the title. E.g.,
        # if we have Dinosaur.Special.Edition, we already know the edition, and
        # we don't need it to appear, duplicated, in the title. Because
        # `_edition_map` returns a (key, value) tuple, we check for the search
        # key here and replace it (not the value).
        if cls._edition_map(source_path)[0] is not None:
            title = re.sub(cls._edition_map(source_path)[0], '', title)

        # Strip all resolution and media tags from the title.
        title = re.sub(patterns.media, '', title)
        title = re.sub(patterns.resolution, '', title)

        # Typical naming patterns place the year as a delimiter between the title
        # and the rest of the file. Therefore we can assume we only care about
        # the first part of the string, and so we split on the year value, and keep
        # only the left-hand portion.
        title = title.split(str(cls.get_year(source_path)))[0]

        # Add back in . to titles or strings we know need to to keep periods.
        # Looking at you, S.W.A.T and After.Life.
        for keep_period_str in config.keep_period:
            title = re.sub(re.compile(r'\b' + re.escape(keep_period_str) + r'\b', re.I), keep_period_str, title)

        # Remove extra whitespace from the edges of the title and remove repeating
        # whitespace.
        title = formatter.strip_extra_whitespace(title.strip())

        return title

    @classmethod
    def get_year(cls, source_path):
        """Get year from full path of file or folder.

        Use regular expressions to identity a year value between 1910 and 2159,
        getting the right-most match if there is more than one year found (looking
        at you, 2001: A Space Odyssey) and not at the start of the input string
        or filename.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A 4-digit integer representing the release year, or None if
            no year could be determined.
        """

        # Ensure source_path is a str
        source_path = str(source_path)

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        # Find all matches of years between 1910 and 2159 (we don't want to
        # match 2160 because 2160p, and hopefully I'll be dead by then and
        # no one will use python anymore). Also convert the matches iterator
        # to a list.
        matches = list(re.finditer(patterns.year, f'{folder}/{file}'))

        # Get the last element, and retrieve the 'year' capture group by name.
        # If there are no matches, return None.
        return int(matches[-1].group('year')) if matches else None

    @classmethod
    def get_edition(cls, source_path):
        """Get and correct special edition from full path of file or folder.

        Iterate a map of strings (or, more aptly, regular expressions) to
        search for, and correct, special editions. This map is defined in
        config.edition_map.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A corrected string representing the film's edition, or None.
        """

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        # Because _edition_map returns a (key, value) tuple, we need to
        # return the second value in the tuple which represents the corrected
        # string value of the edition.
        return cls._edition_map(f'{folder}/{file}')[1] or None

    @classmethod
    def get_resolution(cls, source_path):
        """Get resolution from full path of file or folder.

        Use a regular expression to retrieve release resolutions from the source path
        (e.g. 720p, 1080p, or 2160p).

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A corrected string representing the film's resolution, or None.
        """

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        # Search for any of the known qualities.
        match = re.search(patterns.resolution, f'{folder}/{file}')

        # If a match exists, convert it to lowercase.
        resolution = match.group('resolution').lower() if match else None

        # Manual fix for 4K files
        if resolution == '4k':
            resolution = '2160p'

        # If the resolution doesn't end in p, append p.
        if resolution is not None and 'p' not in resolution:
            resolution += 'p'
            
        return resolution

    @classmethod
    def get_media(cls, source_path) -> Media:
        """Get media from full path of file or folder.

        Use regular expressions to identity the original media of the file.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            An enum representing the media found.
        """

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        match = re.search(patterns.media, f'{folder}/{file}')
        if match and match.group('bluray'):
            return Media.BLURAY
        elif match and match.group('webdl'):
            return Media.WEBDL
        elif match and match.group('hdtv'):
            return Media.HDTV
        elif match and match.group('dvd'):
            return Media.DVD
        elif match and match.group('sdtv'):
            return Media.SDTV
        else:
            return Media.UNKNOWN

    @classmethod
    def is_hdr(cls, source_path) -> bool:
        """Determine whether the media is an HDR file.

        Use regular expressions to identity whether the media is HDR or not.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A bool representing the HDR status of the media.
        """
        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        match = re.search(patterns.hdr, f'{folder}/{file}')
        return True if (match and match.group('hdr')) else False

    @classmethod
    def is_proper(cls, source_path) -> bool:
        """Determine whether the media is a proper rip.

        Use regular expressions to identity whether the file is a proper or not.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A bool representing the proper state of the media.
        """
        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        match = re.search(patterns.proper, f'{folder}/{file}')
        return True if (match and match.group('proper')) else False

    @classmethod
    def get_part(cls, source_path):
        """Get part # from full path of file or folder.

        Use regular expressions to identity the part # of the file.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A string representing the part # of the title, or None, if no
            match is found.
        """

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        # Search for a matching part condition
        match = re.search(patterns.part, f'{folder}/{file}')
        
        # If a match exists, convert it to lowercase.
        return match.group('part').upper() if match else None

    @classmethod
    def _edition_map(cls, source_path):
        """Internal method to search for special edition strings in a source_path.

        This method iterates through config.edition_map, generates regular
        expressions for each potential match, then returns a (key, value)
        tuple containing the first matching regular expression.

        Args:
            source_path: (str, utf-8) full path of file or folder.

        Returns:
            A (key, value) tuple containing either a matching regular expression and its
            corrected counterpart, or (None, None).
        """

        folder = os.path.basename(os.path.dirname(source_path))
        file = os.path.basename(source_path)

        # Iterate over the edition map.
        for key, value in config.edition_map:
            # Generate a regular expression that searches for the search key, separated
            # by word boundaries.
            rx = re.compile(r'\b' + key + r'\b', re.I)
            
            # Because this map is in a specific order, of we find a suitable match, we
            # want to return it right away.
            result = re.search(rx, f'{folder}/{file}')
            if result:
                # Return a tuple containing the matching compiled expression and its
                # corrected value after performing a capture group replace, then break 
                # the loop.
                return (rx, rx.sub(value, result.group()))

        # If no matches are found, return (None, None)
        return (None, None)
