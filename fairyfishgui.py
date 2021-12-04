from contextlib import closing

import PySimpleGUI as sg
import pyffish

MAX_FILES = 12
MAX_RANKS = 10
SQUARE_COLORS = ('#F0D9B5', '#B58863')
PIECE_COLORS = ('white', 'black')


class GameState():
    def __init__(self, variant="chess", start_fen=None, moves=None):
        self.variant = variant
        self.start_fen = start_fen if start_fen else pyffish.start_fen(variant)
        self.moves = moves if moves else []

    def fen(self):
        return pyffish.get_fen(self.variant, self.start_fen, self.moves)

    def legal_moves(self):
        return pyffish.legal_moves(self.variant, self.start_fen, self.moves)

    def is_game_over(self):
        return not self.legal_moves()

    def is_legal(self, move):
        return move in self.legal_moves()

    def filter_legal(self, move, isprefix=False):
        return [m for m in self.legal_moves() if (m.startswith(move) if isprefix else move in m)]

    def to_san(self, move=None):
        if move:
            return pyffish.get_san(self.variant, self.fen(), move)
        return pyffish.get_san_moves(self.variant, self.start_fen, self.moves)

    def push(self, move):
        self.moves.append(move)

    def pop(self):
        if self.moves:
            return self.moves.pop()

    def files(self):
        count = 0
        last_char = ''
        for c in pyffish.start_fen(self.variant).split('/')[0]:
            if c.isdigit():
                count += int(c)
                if last_char.isdigit():
                    count += 9 * int(last_char)
            elif c.isalpha():
                count += 1
            last_char = c
        return count

    def ranks(self):
        return pyffish.start_fen(self.variant).count('/') + 1

    def char_board(self):
        board = []
        rank = []
        prefix = ''
        lastchar = ''
        for c in self.fen():
            if c == ' ':
                board.append(rank)
                break
            elif c == '/':
                board.append(rank)
                rank = []
            elif c.isdigit():
                rank += int(c) * [' ']
                if lastchar.isdigit():
                    rank += 9 * int(lastchar) * [' ']
            elif c == '+':
                prefix = c
            else:
                rank.append(prefix + c)
                prefix = ''
            lastchar = c
        return board


class Board():
    def __init__(self, *args):
        self.state = GameState(*args)

    @staticmethod
    def to_file(file):
        return chr(ord('a') + file)

    def idx2square(self, index):
        return '{}{}'.format(self.to_file(index[1]), self.state.ranks() - index[0])

    def square2idx(self, square):
        return (self.state.ranks() - int(square[1]), ord(square[0]) - ord('a'))

    @staticmethod
    def render_square(key, location):
        square_color = SQUARE_COLORS[(location[0] + location[1]) % 2]
        button = sg.Button(size=(3, 2), button_color=square_color, pad=(0, 0), font='Any 20', key=key)
        return sg.Column([[button]], pad=(0, 0))

    def draw_board(self):
        board_layout = []
        for i in range(MAX_RANKS):
            row = []
            for j in range(MAX_FILES):
                row.append(self.render_square(key=(i, j), location=(i, j)))
            board_layout.append(row)
        return board_layout

    def update_board(self, window):
        char_board = self.state.char_board()
        for i in range(MAX_RANKS):
            for j in range(MAX_FILES):
                elem = window[(i, j)]
                if i >= self.state.ranks() or j >= self.state.files():
                    elem.update(visible=False)
                else:
                    square_color = SQUARE_COLORS[(i + j) % 2]
                    piece = char_board[i][j]
                    elem.update(visible=True, text=piece, button_color=(PIECE_COLORS[piece.islower()], square_color))
        window['_movelist_'].update(' '.join(self.state.to_san()))


class FairyGUI():
    def __init__(self):
        menu_def = [['&File', ['&Exit']], ['&Help', '&About...']]

        sg.ChangeLookAndFeel('GreenTan')

        board_controls = [[sg.Button('New Game', key='_newgame_'), sg.Button('Load variants', key='_variants_')],
                        [sg.Button('Set FEN', key='_set_fen_'), sg.Button('Reset', key='_reset_')],
                        [sg.Button('Move', key='_move_'), sg.Button('Undo', key='_undo_')],
                        [sg.Text('Move List')],
                        [sg.Multiline(do_not_clear=True, autoscroll=True, size=(15, 10), key='_movelist_')],
                        ]

        self.board = Board()
        board_tab = [[sg.Column(self.board.draw_board())]]

        layout = [[sg.Menu(menu_def, tearoff=False)],
                [sg.TabGroup([[sg.Tab('Board', board_tab)]], title_color='red'),
                sg.Column(board_controls)]]

        self.window = sg.Window('FairyFishGUI',
                        default_button_element_size=(12, 1),
                        auto_size_buttons=False,
                        resizable=True).Layout(layout)

    @staticmethod
    def popup(element, header, data, **kwargs):
        layout = [[element(data, key='entry', **kwargs)], [sg.Button('OK')]]
        with closing(sg.Window(header, layout).finalize()) as window:
            while True:
                event, values = window.read()
                if event == sg.WINDOW_CLOSED or event == 'OK':
                    if values and values['entry']:
                        return values['entry']
                    return

    def run(self):
        self.window.finalize()
        while True:
            self.board.update_board(self.window)
            move_from = None
            while True:
                button, value = self.window.Read()
                if button in (None, 'Exit'):
                    exit()
                elif button == '_newgame_':
                    variant = self.popup(sg.Listbox, 'Variant', pyffish.variants(), size=(30, 20))
                    if variant:
                        self.board.state = GameState(variant[0])
                        break
                elif button == '_set_fen_':
                    fen = sg.popup_get_text('Set FEN', default_text=self.board.state.fen(), size=(80, 20))
                    if fen:
                        self.board.state = GameState(self.board.state.variant, fen)
                        break
                elif button == '_reset_':
                    self.board.state = GameState(self.board.state.variant)
                    break
                elif button == '_undo_':
                    self.board.state.pop()
                    self.board.update_board(self.window)
                elif button == '_variants_':
                    variant_path = sg.popup_get_file('Select variants.ini',
                                               file_types=(('variant configuration file', '*.ini'),))
                    if variant_path:
                        with open(variant_path) as variants_ini:
                            pyffish.load_variant_config(variants_ini.read())
                elif type(button) is tuple or button == '_move_':
                    if move_from or button == '_move_':
                        squares = []
                        if move_from:
                            squares.append(self.board.idx2square(move_from))
                        if type(button) is tuple:
                            squares.append(self.board.idx2square(button))
                        moves = list(set(self.board.state.filter_legal(''.join(squares))
                                         + self.board.state.filter_legal(''.join(reversed(squares)))))
                        if len(moves) > 0:
                            if len(moves) > 1:
                                moves = self.popup(sg.Listbox, 'Choose move', moves, size=(20, 10))
                            if moves:
                                move = moves[0]
                                self.board.state.push(move)
                        move_from = None
                        self.board.update_board(self.window)
                    else:
                        moves = self.board.state.filter_legal(self.board.idx2square(button))
                        if moves:
                            for move in moves:
                                if '@' not in move:
                                    to_sq = self.board.square2idx(move[0:2])
                                    self.window[to_sq].update(button_color='cyan')
                            move_from = button
                            self.window[move_from].update(button_color='green')
                            for move in self.board.state.filter_legal(self.board.idx2square(button), True):
                                to_sq = self.board.square2idx(move[2:4])
                                self.window[to_sq].update(button_color='yellow' if self.window[to_sq].get_text().isspace() else 'red')


if __name__ == '__main__':
    FairyGUI().run()
