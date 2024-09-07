import itertools
import re

from talon import Context, Module, actions, settings

ctx = Context()
mod = Module()


mod.setting(
    "text_navigation_max_line_search",
    type=int,
    default=2,  
    desc="The maximum number of rows that will be included in the search for the keywords above and below in <user direction>",
)

mod.list("navigation_action",desc="Actions to perform, e.g. move, select, cut...")
mod.list("before_or_after",desc="Indicates if cursor should go before or after ref. pt.")
mod.list("navigation_target_name",desc="Names for regular expressions for common things to navigate to, for instance a word with or without underscores",
)

ctx.lists["self.navigation_action"] = {
    "move": "GO",
    "extend": "EXTEND",
    "select": "SELECT",
    "clear": "DELETE",
    "cut": "CUT",
    "copy": "COPY",
}
ctx.lists["self.before_or_after"] = {
    "before": "BEFORE",
    "after": "AFTER",
    # DEFAULT is also a valid option as input for this capture, but is not directly accessible for the user.
}
navigation_target_names = {
    "word": r"\w+",
    "small": r"[A-Z]?[a-z0-9]+",
    "big": r"[\S]+",
    "parens": r"\((.*?)\)",
    "squares": r"\[(.*?)\]",
    "braces": r"\{(.*?)\}",
    "quotes": r"\"(.*?)\"",
    "angles": r"\<(.*?)\>",
    # "single quotes": r'\'(.*?)\'',
    "all": r"(.+)",
    "method": r"\w+\((.*?)\)",
    "constant": r"[A-Z_][A-Z_]+",
}
ctx.lists["self.navigation_target_name"] = navigation_target_names


@mod.capture(
    rule="<user.any_alphanumeric_key> | {user.navigation_target_name} | (abbreviate|abbreviation|brief) {user.abbreviation} | phrase <user.text> | variable {user.variable_list} | function {user.function_list} | <user.text>"
)
def navigation_target(m) -> re.Pattern:
    """A target to navigate to. Returns a regular expression."""
    if hasattr(m, "any_alphanumeric_key"):
        return re.compile(re.escape(m.any_alphanumeric_key), re.IGNORECASE)
    if hasattr(m, "navigation_target_name"):
        return re.compile(m.navigation_target_name)
    if hasattr(m,"abbreviation"):
        t = m.abbreviation
    if hasattr(m,"variable_list"):
        t = m.variable_list
    if hasattr(m,"function_list"):
        t = m.function_list
    if hasattr(m,"text"):
        t = m.text
        # include homophones
        word_list = re.findall(r"\w+",t)
        word_list = set(word_list)
        for w in word_list:
            phone_list = actions.user.homophones_get(w)
            if phone_list:
                t = t.replace(w,"(" + '|'.join(phone_list) + ")")
    r = re.compile(t, re.IGNORECASE)
    return r


@mod.action_class
class Actions:
    def navigation_by_string(
        navigation_action: str,  # GO, EXTEND, SELECT, DELETE, CUT, COPY
        direction: str,  # up, down, left, right
        navigation_target_name: str,
        before_or_after: str,  # BEFORE, AFTER, DEFAULT
        search_string: str,
        occurrence_number: int
    ):
        """Just enter a string to search for instead of a complicated capture"""
        print("FUNCTION: navigation_by_string")
        actions.user.navigation(
            navigation_action,
            direction,
            navigation_target_name,
            before_or_after,
            re.compile(re.escape(search_string), re.IGNORECASE),
            occurrence_number
        )
    def navigation_by_word(
        navigation_action: str,  # GO, EXTEND, SELECT, DELETE, CUT, COPY
        direction: str,  # up, down, left, right
        navigation_target_name: str,
        before_or_after: str,  # BEFORE, AFTER, DEFAULT
        search_string: str,
        occurrence_number: int
    ):
        """Search for a word including its homophones"""
        print("FUNCTION: navigation_by_word")
        phone_list = actions.user.homophones_get(search_string)
        print(f"word: {search_string}, phones: {phone_list}")
        if phone_list == None:
            regex = re.compile(re.escape(search_string), re.IGNORECASE)
        else:
            regex = re.compile('|'.join(map(re.escape, phone_list)), re.IGNORECASE)
        print(f"regex: {regex}")
        actions.user.navigation(
            navigation_action,
            direction,
            navigation_target_name,
            before_or_after,
            regex,
            occurrence_number
        )
    def navigation(
        navigation_action: str,  # GO, EXTEND, SELECT, DELETE, CUT, COPY
        direction: str,  # up, down, left, right
        navigation_target_name: str,
        before_or_after: str,  # BEFORE, AFTER, DEFAULT
        regex: re.Pattern,
        occurrence_number: int,
    ):
        """Navigate in `direction` to the occurrence_number-th time that `regex` occurs, then execute `navigation_action` at the given `before_or_after` position."""
        
        direction = direction.upper()
#        print(f"direction: {direction}")
        navigation_target_name = re.compile(
            navigation_target_names["word"]
            if (navigation_target_name == "DEFAULT")
            else navigation_target_name
        )
        function = navigate_left if direction in ("UP", "LEFT") else navigate_right
        function(
            navigation_action,
            navigation_target_name,
            before_or_after,
            regex,
            occurrence_number,
            direction,
        )

    def navigation_by_name(
        navigation_action: str,  # GO, EXTEND, SELECT, DELETE, CUT, COPY
        direction: str,  # up, down, left, right
        before_or_after: str,  # BEFORE, AFTER, DEFAULT
        navigation_target_name: str,  # word, big, small
        occurrence_number: int,
    ):
        """Like user.navigation, but to a named target."""
        r = re.compile(navigation_target_names[navigation_target_name])
        actions.user.navigation(
            navigation_action,
            direction,
            "DEFAULT",
            before_or_after,
            r,
            occurrence_number,
        )


def get_text_left():
    # get text on the same line to the left of cursor
    actions.edit.extend_line_start()
    text = actions.edit.selected_text()
    actions.edit.right()
    return text


def get_text_right():
    # get text on the same line to the right of cursor
    actions.edit.extend_line_end()
    text = actions.edit.selected_text()
    actions.edit.left()
    return text


def get_text_up():
    # get text on the same line to the left and on previous lines
    actions.edit.extend_line_start()
    actions.edit.extend_left()
    for j in range(0, settings.get("user.text_navigation_max_line_search")):
        actions.edit.extend_up()
    actions.edit.extend_line_start()
    text = actions.edit.selected_text()
    actions.edit.right()
    return text


def get_text_down():
    # get text on the same line to the right and on subsequent lines
    actions.edit.extend_line_end()
    actions.edit.extend_right()
    for j in range(0, settings.get("user.text_navigation_max_line_search")):
        actions.edit.extend_down()
    actions.edit.extend_line_end()
    text = actions.edit.selected_text()
    actions.edit.left()
    return text


def get_current_selection_size():
    return len(actions.edit.selected_text())


def go_right(i):
    for j in range(0, i):
        actions.edit.right()


def go_left(i):
    for j in range(0, i):
        actions.edit.left()


def extend_left(i):
    for j in range(0, i):
        actions.edit.extend_left()


def extend_right(i):
    for j in range(0, i):
        actions.edit.extend_right()


def select(direction, start, end, length):
    if direction == "RIGHT" or direction == "DOWN":
        go_right(start)
        extend_right(end - start)
    else:
        go_left(length - end)
        extend_left(end - start)


def navigate_left(
    navigation_action,
    navigation_target_name,
    before_or_after,
    regex,
    occurrence_number,
    direction,
):

    # record information about current selection so that we can 
    # reselect later if needed
    current_selection_length = get_current_selection_size()
    if current_selection_length > 0:
        actions.edit.right()
    # get text to search within,1
    text = get_text_left() if direction == "LEFT" else get_text_up()
    # only search in the text that was not selected
    subtext = (
        text if current_selection_length <= 0 else text[:-current_selection_length]
    )
    # look for a match. return value is a regex march object
    match = match_backwards(regex, occurrence_number, subtext)
    if match is None:
        # put back the old selection, if the search failed
        extend_left(current_selection_length)
        return
    # get indices of start and end of matching sub string
    start = match.start()
    end = match.end()
    # With these indices we can now pull out the target string from the text we selected to search within
    handle_navigation_action(
        navigation_action,
        navigation_target_name,
        before_or_after,
        direction,
        text,
        start,
        end,
    )


def navigate_right(
    navigation_action,
    navigation_target_name,
    before_or_after,
    regex,
    occurrence_number,
    direction,
):
    current_selection_length = get_current_selection_size()
    if current_selection_length > 0:
        actions.edit.left()
    text = get_text_right() if direction == "RIGHT" else get_text_down()
    # only search in the text that was not selected
    sub_text = text[current_selection_length:]
    # pick the next interrater, Skip n number of occurrences, get an iterator given the Regex
    match = match_forward(regex, occurrence_number, sub_text)
    if match is None:
        # put back the old selection, if the search failed
        extend_right(current_selection_length)
        return
    start = current_selection_length + match.start()
    end = current_selection_length + match.end()
    # Now that we have the start and and
    handle_navigation_action(
        navigation_action,
        navigation_target_name,
        before_or_after,
        direction,
        text,
        start,
        end,
    )


def handle_navigation_action(
    navigation_action,
    navigation_target_name,
    before_or_after,
    direction,
    text,
    start,
    end,
):
    # Call the appropriate function based on the navigation action_class
    
    # I suspect that errors are the result of this starting too quickly,
    # so I'm gonna force a short sleep here
    actions.sleep(0.2)
    length = len(text)
    if navigation_action == "GO":
        handle_move(direction, before_or_after, start, end, length)
    elif navigation_action == "SELECT":
        handle_select(
            navigation_target_name, before_or_after, direction, text, start, end, length
        )
    elif navigation_action == "DELETE":
        handle_select(
            navigation_target_name, before_or_after, direction, text, start, end, length
        )
        actions.edit.delete()
    elif navigation_action == "CUT":
        handle_select(
            navigation_target_name, before_or_after, direction, text, start, end, length
        )
        actions.edit.cut()
    elif navigation_action == "COPY":
        handle_select(
            navigation_target_name, before_or_after, direction, text, start, end, length
        )
        actions.edit.copy()
    elif navigation_action == "EXTEND":
        handle_extend(before_or_after, direction, start, end, length)


def handle_select(
    navigation_target_name, before_or_after, direction, text, start, end, length
):
    if before_or_after == "BEFORE":
        select_left = length - start
        text_left = text[:-select_left]
        match2 = match_backwards(navigation_target_name, 1, text_left)
        if match2 is None:
            end = start
            start = 0
        else:
            start = match2.start()
            end = match2.end()
    elif before_or_after == "AFTER":
        text_right = text[end:]
        match2 = match_forward(navigation_target_name, 1, text_right)
        if match2 is None:
            start = end
            end = length
        else:
            start = end + match2.start()
            end = end + match2.end()
    select(direction, start, end, length)


def handle_move(direction, before_or_after, start, end, length):
    if direction == "RIGHT" or direction == "DOWN":
        if before_or_after == "BEFORE":
            go_right(start)
        else:
            go_right(end)
    else:
        if before_or_after == "AFTER":
            go_left(length - end)
        else:
            go_left(length - start)


def handle_extend(before_or_after, direction, start, end, length):
    if direction == "RIGHT" or direction == "DOWN":
        if before_or_after == "BEFORE":
            extend_right(start)
        else:
            extend_right(end)
    else:
        if before_or_after == "AFTER":
            extend_left(length - end)
        else:
            extend_left(length - start)


def match_backwards(regex, occurrence_number, subtext):
    try:
        match = list(regex.finditer(subtext))[-occurrence_number]
        return match
    except IndexError:
        return


def match_forward(regex, occurrence_number, sub_text):
    try:
        match = next(
            itertools.islice(regex.finditer(sub_text), occurrence_number - 1, None)
        )
        return match
    except StopIteration:
        return None
