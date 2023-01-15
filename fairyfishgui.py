from collections import OrderedDict, Counter
from collections.abc import Iterable
from contextlib import closing
import subprocess
import threading
import re

import PySimpleGUI as sg
import pyffish


MAX_FILES = 12
MAX_RANKS = 10
WHITE, BLACK = 0, 1
POCKET = 'pocket'
SQUARE_COLORS = ('#F0D9B5', '#B58863', '#808080', '#9FB8AD')  # light, dark, wall, pocket
PIECE_COLORS = ('white', 'black')
WALL_CHAR = '*'


def piece_color(piece):
    return piece.islower()


class Move():
    PATTERN = re.compile(r'(\+)?(?P<fromto>(?P<from>[A-Z]@|[a-z]\d+)(?P<to>[a-z]\d+))([a-z+-])?(,(?P<fromto2>(?P<from2>[a-z]\d+)(?P<to2>[a-z]\d+)))?')

    def __init__(self, move):
        self.match = self.PATTERN.fullmatch(move)

    def contains(self, squares):
        return not squares or (squares[0] in (self.from_sq, self.to_sq)
            and (len(squares) < 2 or (squares[1] in (self.from_sq, self.to_sq) and (squares[0] != squares[1] or self.from_sq == self.to_sq))
            and (len(squares) < 3 or squares[2] in (self.from_sq2, self.to_sq2)
            and (len(squares) < 4 or squares[3] == self.to_sq2))))

    @property
    def from_sq(self):
        return self.match.group('from')

    @property
    def to_sq(self):
        return self.match.group('to')

    @property
    def from_sq2(self):
        return self.match.group('from2')

    @property
    def to_sq2(self):
        return self.match.group('to2')

    @property
    def fromto2(self):
        return self.match.group('fromto2')


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
            message += 'setoption name {} value {}\n'.format(option, value)
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
        # OrderedDict here to store the order of the captured pieces, 
        # so that the pocket won't vary for each update
        self.pockets = {WHITE: OrderedDict(), BLACK: OrderedDict()}

    def fen(self):
        return pyffish.get_fen(self.variant, self.start_fen, self.moves)

    def side_to_move(self):
        return int(self.fen().split()[1] == 'b')

    def legal_moves(self):
        return pyffish.legal_moves(self.variant, self.start_fen, self.moves)

    def is_game_over(self):
        return not self.legal_moves()

    def is_legal(self, move):
        return move in self.legal_moves()

    def filter_legal(self, squares):
        return [m for m in self.legal_moves() if Move(m).contains(squares)]

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
            elif c.isalpha() or c in WALL_CHAR:
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
            elif c == '~':
                prefix = ''
                lastchar = ''
                continue
            else:
                rank.append(prefix + c)
                prefix = ''
            lastchar = c
        return board

    def update_pockets(self):
        # clear all the pocket pieces, keep the keys
        for pocket in self.pockets.values():
            for piece in pocket:
                pocket[piece] = 0

        # determine new counts
        pocket_pieces = re.findall(r"\[(.*)\]", self.fen())
        pocket_counts = Counter(pocket_pieces[0] if pocket_pieces else '')

        for piece, count in pocket_counts.items():
            self.pockets[piece_color(piece)][piece.upper()] = count


class Board():
    def __init__(self, *args):
        self.state = GameState(*args)

    @staticmethod
    def to_file(file):
        return chr(ord('a') + file)

    def idx2square(self, index):
        if type(index) is tuple and index and index[0] == POCKET:
            # piece drop
            return list(self.state.pockets[index[1]].keys())[index[2]] + '@'
        return '{}{}'.format(self.to_file(index[1]), self.state.ranks() - index[0])

    def square2idx(self, square):
        if square[-1] == '@':
            # piece drop
            color = self.state.side_to_move()
            return (POCKET, color, list(self.state.pockets[color].keys()).index(square[-2]))
        return (self.state.ranks() - int(square[1:]), ord(square[0]) - ord('a'))

    @staticmethod
    def render_square(key):
        font_size = min(sg.Window.get_screen_size()) // 50
        font_size_sub = font_size // 2
        layout = [sg.Button(size=(3, 2), pad=(0, 0), font='Any {}'.format(font_size), key=key)]
        if key[0] == POCKET:
            # +---+---+---+---+
            # | P | N |   | R |
            # +---+---+---+---+ ...
            # | 3 | 1 |   | 2 |
            # +---+---+---+---+
            layout.append(sg.Text(size=(2, 1), pad=(0, 0), text_color='red', font='Any {}'.format(font_size_sub), key=('count',) + key))
        return sg.pin(sg.Column([layout], pad=(0, 0), key=('col',) + key))

    def draw_board(self):
        board_layout = []
        for i in range(MAX_RANKS):
            row = []
            for j in range(MAX_FILES):
                row.append(self.render_square(key=(i, j)))
            board_layout.append(row)
        return board_layout

    def draw_pocket(self, pocket_color):
        pocket_layout = []
        for i in range(MAX_FILES):
            pocket_layout.append(self.render_square(key=(POCKET, pocket_color, i,)))
        return pocket_layout

    def update(self, window):
        char_board = self.state.char_board()
        for i in range(MAX_RANKS):
            for j in range(MAX_FILES):
                elem = window[(i, j)]
                col = window[('col', i, j)]
                if i >= self.state.ranks() or j >= self.state.files():
                    col.update(visible=False)
                else:
                    piece = char_board[i][j]
                    text_color = PIECE_COLORS[piece_color(piece)]
                    square_color = SQUARE_COLORS[(i + j) % 2 if piece not in WALL_CHAR else 2]
                    elem.update(text=piece if piece not in WALL_CHAR else '', button_color=(text_color, square_color))
                    col.update(visible=True)

        # update pocket
        for color, pieces in self.state.pockets.items():
            for i in range(MAX_FILES):
                key = (POCKET, color, i)
                elem = window[key]
                num = window[('count',) + key]
                col = window[('col',) + key]
                if i >= len(pieces):
                    col.update(visible=False)
                else:  # type(pieces) = OrderedDict
                    piece, piece_count = list(pieces.items())[i]
                    if piece_count > 0:
                        elem.update(text=piece, visible=True, button_color=(PIECE_COLORS[color], SQUARE_COLORS[3]))
                        num.update(piece_count, visible=True)
                        col.update(visible=True)
                    else:
                        elem.update(visible=False)
                        num.update(visible=False)

        window['_movelist_'].update(' '.join(self.state.to_san()))

class FairyGUI():
    def __init__(self):
        menu_def = [['&File', ['&Exit']], ['&Help', '&About...'], ['&Settings', '&Engine Settings']]

        sg.ChangeLookAndFeel('GreenTan')

        board_controls = [[sg.Button('New Game', key='_newgame_'), sg.Button('Load variants', key='_variants_')],
                          [sg.Button('Load engine', key='_engine_'), sg.Button('Engine on/off', key='_toggle_')],
                          [sg.Button('Set FEN', key='_set_fen_'),sg.Button('Reset', key='_reset_')],
                          [sg.Button('Move', key='_move_'),sg.Button('Undo', key='_undo_')],
                          [sg.Text('Move List')],
                          [sg.Multiline(do_not_clear=True, autoscroll=True, size=(25, 10), key='_movelist_')],
                          [sg.Text('Engine Output')],
                          [sg.Multiline(do_not_clear=True, autoscroll=True, size=(25, 10), key='_engine_output_')],
                          ]

        self.board = Board()
        board_tab = [[sg.Column([self.board.draw_pocket(BLACK)])], [sg.Column(self.board.draw_board())],[sg.Column([self.board.draw_pocket(WHITE)])]]
        self.current_selection = []
        self.engine = None
        self.engine_thread = None
        # TODO: read defaults from uci output
        self.engine_settings = {'EvalFile': '', 'Threads': ''}

        layout = [[sg.Menu(menu_def, tearoff=False)],
                  [sg.TabGroup([[sg.Tab('Board', board_tab)]], title_color='red'),
                   sg.Column(board_controls)]]

        self.window = sg.Window('FairyFishGUI',
                                default_button_element_size=(12, 1),
                                auto_size_buttons=False,
                                resizable=True).Layout(layout)

    @staticmethod
    def popup(element, header, data, **kwargs):
        layout = [[element(data, key='entry', **kwargs)], [sg.Button('OK', bind_return_key=True)]]
        with closing(sg.Window(header, layout).finalize()) as window:
            while True:
                event, values = window.read()
                if event == sg.WINDOW_CLOSED or event == 'OK':
                    if values and values['entry']:
                        return values['entry']
                    return

    @staticmethod
    def engine_settings_panel():
        layout = [[sg.Text('Chose NNUE file:')],
                  [sg.Input(key='EvalFile'), sg.FileBrowse(key='_nnue_', target='EvalFile', file_types=(('nnue file', '*.nnue'),))],
                  [sg.Text('Threads: (The number of CPU threads used for searching)')],
                  [sg.Input(key='Threads')],
                  [sg.Button('OK')]]
        with closing(sg.Window('Optional Settings', layout).finalize()) as window:
            while True:
                event, values = window.read()
                if event == sg.WINDOW_CLOSED or event == 'OK':
                    if values:
                        if values['Threads'] and not values['Threads'].isdigit():
                            sg.popup_ok('Threads should be a positive integer')
                            continue
                        return values
                    return

    def process_square(self, square_idx=None, force_move=False):
        if square_idx:
            self.current_selection.append(square_idx)
        squares = [self.board.idx2square(idx) for idx in self.current_selection]
        moves = self.board.state.filter_legal(squares)
        if square_idx:
            if len(self.current_selection) == 1:
                # first square selection
                if not moves:
                    self.current_selection.clear()
                    return
                for move in moves:
                    to_sq = self.board.square2idx(Move(move).to_sq)
                    self.window[to_sq].update(button_color='yellow' if self.window[to_sq].get_text().isspace() else 'red')
                for move in moves:
                    try:
                        from_sq = self.board.square2idx(Move(move).from_sq)
                    except ValueError:
                        # ignore missing pocket for freeDrops, e.g., in ataxx
                        pass
                    else:
                        self.window[from_sq].update(button_color='cyan')
                self.window[square_idx].update(button_color='green')
            elif len(moves) > 1:
                # ambiguous second, third, or fourth selection
                # is further disambiguation possible by selecting another square?
                if all(',' in move for move in moves) and len(set(Move(move).fromto2 for move in moves)) > 1:
                    self.window[square_idx].update(button_color='green')
                    # mark selection for multi-leg moves
                    for move in moves:
                        to_sq2 = self.board.square2idx(Move(move).to_sq2)
                        self.window[to_sq2].update(button_color='orange')
                else:
                    force_move = True

        # disambiguate moves
        if force_move and len(moves) > 1:
            moves = self.popup(sg.Listbox, 'Choose move', moves, size=(20, 10))

        # update board depending on selection
        if not moves:
            # reset
            self.update_board()
        elif len(moves) == 1 and (force_move or len(self.current_selection) != 1 or squares[0] != Move(moves[0]).from_sq):
            # make move if unique (unless the clicked piece only has one move)
            self.update_board(move=moves[0])
        else:
            # wait for next selection
            assert not force_move

    def quit_engine(self):
        if self.engine:
            self.engine.quit()

    def load_engine(self, engine_path):
        self.quit_engine()
        self.engine = Engine([engine_path], options=self.engine_settings)
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
        self.engine.initialize()
        self.engine.setoption('UCI_Variant', self.board.state.variant)
        self.engine.newgame()
        self.engine.position(self.board.state.start_fen, self.board.state.moves)
        self.engine.analyze()

    def set_engine_options(self, options):
        if self.engine and not self.engine.paused:
            self.engine.stop()
            self.engine.paused = False
        for key, value in options.items():
            if key in self.engine_settings and value:
                self.engine_settings[key] = value
                if self.engine:
                    self.engine.setoption(key, value)
        if self.engine and not self.engine.paused:
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

        self.current_selection.clear()
        self.board.state.update_pockets()
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
            elif button == 'Engine Settings':
                settings = self.engine_settings_panel()
                if settings:
                    self.set_engine_options(settings)
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
                variant_path = sg.popup_get_file('Select variants.ini', file_types=(('variant configuration file', '*.ini'),))
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
            elif type(button) is tuple:
                self.process_square(button)
            elif button == '_move_':
                self.process_square(force_move=True)


if __name__ == '__main__':
    FairyGUI().run()
