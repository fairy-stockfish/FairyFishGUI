from collections import defaultdict
from collections.abc import Iterable
from contextlib import closing
import subprocess
import threading

import PySimpleGUI as sg
import pyffish

MAX_FILES = 12
MAX_RANKS = 10
SQUARE_COLORS = ('#F0D9B5', '#B58863')
PIECE_COLORS = ('white', 'black')


class Engine():
    INFO_KEYWORDS = {'depth': int, 'seldepth': int, 'multipv': int, 'nodes': int, 'nps': int, 'time': int, 'score': list, 'pv': list}

    def __init__(self, args, options=None):
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
        self.lock = threading.Lock()
        self.options = options
        self.paused = False

    def write(self, message):
        with self.lock:
            self.process.stdin.write(message)
            self.process.stdin.flush()

    def setoption(self, name, value):
        self.write('setoption name {} value {}\n'.format(name, value))

    def initialize(self):
        message = 'uci\n'
        for option, value in self.options.items():
            message += self.process.stdin.write('setoption name {} value {}\n'.format(option, value))
        self.write(message)

    def newgame(self):
        self.write('ucinewgame\n')

    def position(self, fen=None, moves=None):
        fen = 'fen {}'.format(fen) if fen else 'startpos'
        moves = 'moves {}'.format(' '.join(moves)) if moves else ''
        self.write('position {} {}\n'.format(fen, moves))

    def analyze(self):
        self.write('go infinite\n')
        self.paused = False

    def stop(self):
        self.write('stop\n')
        self.paused = True

    def toggle(self):
        if self.paused:
            self.analyze()
        else:
            self.stop()

    def quit(self):
        self.write('quit\n')

    def read(self):
        while self.process.poll() is None:
            yield self.process.stdout.readline()

    @classmethod
    def process_line(cls, line):
        items = line.split()
        if len(items) > 1 and items[0] == 'info' and items[1] != 'string':
            key = None
            values = []
            info = {}
            for i in items[1:] + ['']:
                if not i or i in cls.INFO_KEYWORDS:
                    if key:
                        if values and not issubclass(cls.INFO_KEYWORDS[key], Iterable):
                            values = values[0]
                        info[key] = cls.INFO_KEYWORDS[key](values)
                    key = i
                    values = []
                else:
                    values.append(i)
            return info
        return None

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

    def filter_legal(self, move):
        return [m for m in self.legal_moves() if not move or (move in m and move + '0' not in m)]  # workaround for rank 10

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
        return (self.state.ranks() - int(square[1:]), ord(square[0]) - ord('a'))

    @staticmethod
    def render_square(key, location):
        square_color = SQUARE_COLORS[(location[0] + location[1]) % 2]
        font_size = min(sg.Window.get_screen_size()) // 50
        button = sg.Button(size=(3, 2), button_color=square_color, pad=(0, 0), font='Any {}'.format(font_size), key=key)
        return sg.pin(sg.Column([[button]], pad=(0, 0), key=('col',) + key))

    def draw_board(self):
        board_layout = []
        for i in range(MAX_RANKS):
            row = []
            for j in range(MAX_FILES):
                row.append(self.render_square(key=(i, j), location=(i, j)))
            board_layout.append(row)
        return board_layout

    def update(self, window):
        self.current_selection = None
        char_board = self.state.char_board()
        for i in range(MAX_RANKS):
            for j in range(MAX_FILES):
                elem = window[(i, j)]
                col = window[('col', i, j)]
                if i >= self.state.ranks() or j >= self.state.files():
                    col.update(visible=False)
                else:
                    square_color = SQUARE_COLORS[(i + j) % 2]
                    piece = char_board[i][j]
                    elem.update(text=piece, button_color=(PIECE_COLORS[piece.islower()], square_color))
                    col.update(visible=True)
        window['_movelist_'].update(' '.join(self.state.to_san()))


class FairyGUI():
    def __init__(self):
        menu_def = [['&File', ['&Exit']], ['&Help', '&About...']]

        sg.ChangeLookAndFeel('GreenTan')

        board_controls = [[sg.Button('New Game', key='_newgame_'), sg.Button('Load variants', key='_variants_')],
                        [sg.Button('Load engine', key='_engine_'), sg.Button('Engine on/off', key='_toggle_')],
                        [sg.Button('Set FEN', key='_set_fen_'), sg.Button('Reset', key='_reset_')],
                        [sg.Button('Move', key='_move_'), sg.Button('Undo', key='_undo_')],
                        [sg.Text('Move List')],
                        [sg.Multiline(do_not_clear=True, autoscroll=True, size=(25, 10), key='_movelist_')],
                        [sg.Text('Engine Output')],
                        [sg.Multiline(do_not_clear=True, autoscroll=True, size=(25, 10), key='_engine_output_')],
                        ]

        self.board = Board()
        board_tab = [[sg.Column(self.board.draw_board())]]
        self.current_selection = None
        self.engine = None
        self.engine_thread = None

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

    def process_square(self, button):
        if self.current_selection or button == '_move_':
            squares = [self.board.idx2square(square) for square in (self.current_selection, button) if type(square) is tuple]
            moves = list(set(self.board.state.filter_legal(''.join(squares))
                                + self.board.state.filter_legal(''.join(reversed(squares)))))
            self.current_selection = None
            if len(moves) > 0:
                if len(moves) > 1:
                    moves = self.popup(sg.Listbox, 'Choose move', moves, size=(20, 10))
                if moves:
                    return moves[0]
            self.update_board()
        else:
            moves = self.board.state.filter_legal(self.board.idx2square(button))
            if moves:
                for move in moves:
                    to_sq = self.board.square2idx(move[2 + move[2].isdigit():len(move) - (not move[-1].isdigit())])
                    self.window[to_sq].update(button_color='yellow' if self.window[to_sq].get_text().isspace() else 'red')
                for move in moves:
                    if '@' not in move:
                        to_sq = self.board.square2idx(move[0:2 + move[2].isdigit()])
                        self.window[to_sq].update(button_color='cyan')
                self.window[button].update(button_color='green')
                self.current_selection = button

    def quit_engine(self):
        if self.engine:
            self.engine.quit()

    def load_engine(self, engine_path):
        self.quit_engine()
        self.engine = Engine([engine_path])
        def read_output():
            def format_score(score):
                return '#{}'.format(score[1]) if score[0] == 'mate' else '{:.2f}'.format(int(score[1]) / 100) if score[0] == 'cp' else None
            def format_info(info):
                return '{}\t{}\t{}'.format(info.get('depth'), format_score(info.get('score')), ' '.join(info.get('pv', [])))
            multipv = {}
            try:
                for line in self.engine.read():
                    info = self.engine.process_line(line)
                    if info and 'score' in info:
                        multipv[info.get('multipv', 1)] = info
                        for multipvidx in sorted(multipv):
                            self.window['_engine_output_'].update(format_info(multipv[multipvidx]))
            except RuntimeError:
                pass
        self.engine_thread = threading.Thread(target=read_output, daemon=True)
        self.engine_thread.start()
        self.engine.setoption('UCI_Variant', self.board.state.variant)
        self.engine.newgame()
        self.engine.position(self.board.state.start_fen, self.board.state.moves)
        self.engine.analyze()

    def update_board(self, variant=None, fen=None, move=None, undo=False):
        if self.engine and not self.engine.paused and (variant or fen or move or undo):
            self.engine.stop()
            self.engine.paused = False

        if variant:
            self.board.state = GameState(variant)
            if self.engine:
                self.engine.setoption('UCI_Variant', variant)
                self.engine.newgame()
                self.engine.position()
        if fen:
            self.board.state = GameState(self.board.state.variant, fen)
            if self.engine:
                self.engine.position(fen)
        if move:
            self.board.state.push(move)
            if self.engine:
                self.engine.position(self.board.state.start_fen, self.board.state.moves)
        if undo:
            self.board.state.pop()
            if self.engine:
                self.engine.position(self.board.state.start_fen, self.board.state.moves)

        if self.engine and not self.engine.paused and (variant or fen or move or undo):
            self.engine.analyze()

        self.board.update(self.window)

    def run(self):
        self.window.finalize()
        self.update_board()
        while True:
            button, value = self.window.Read()
            if button in (None, 'Exit', sg.WIN_CLOSED):
                self.quit_engine()
                exit()
            elif button == 'About...':
                sg.popup('FairyFishGUI by Fabian Fichter\n\nhttps://github.com/ianfab/FairyFishGUI', title='About')
            elif button == '_newgame_':
                variant = self.popup(sg.Listbox, 'Variant', pyffish.variants(), size=(30, 20))
                if variant:
                    self.update_board(variant=variant[0])
            elif button == '_set_fen_':
                fen = sg.popup_get_text('Set FEN', default_text=self.board.state.fen(), size=(80, 20))
                if fen:
                    self.update_board(fen=fen)
            elif button == '_reset_':
                self.update_board(variant=self.board.state.variant)
            elif button == '_undo_':
                self.update_board(undo=True)
            elif button == '_variants_':
                variant_path = sg.popup_get_file('Select variants.ini',
                                            file_types=(('variant configuration file', '*.ini'),))
                if variant_path:
                    with open(variant_path) as variants_ini:
                        pyffish.load_variant_config(variants_ini.read())
                    if self.engine:
                        self.engine.setoption('VariantPath', variant_path)
            elif button == '_engine_':
                engine_path = sg.popup_get_file('Select engine')
                if engine_path:
                    self.load_engine(engine_path)
            elif button == '_toggle_':
                if self.engine:
                    self.engine.toggle()
            elif type(button) is tuple or button == '_move_':
                move = self.process_square(button)
                if move:
                    self.update_board(move=move)


if __name__ == '__main__':
    FairyGUI().run()
