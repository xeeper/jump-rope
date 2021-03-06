import pandas as pd

MILLI = 1000

MAN_HEIGHT_M = 1.7
EARTH_GRAVITY = 9.81
ACCELERATION_ERROR = .5 * EARTH_GRAVITY
INTERPOLATION_SPAN = 100
MAX_MILLISECONDS_BETWEEN_JUMPS = 800

MIN_N_FRAMES = 4


class JumpCounter:
    def __init__(self):
        self._timestamps = []
        self._boxes = []
        self._all_timestamps = []
        self._all_boxes = []
        self._count = 0
        self._last_jump_timestamp = None

    def _is_height_change(self, new_box):
        return self._boxes and new_box[3] != self._boxes[-1][3]

    def _check_for_jump(self):
        df = self.df
        m_to_p_ratio = MAN_HEIGHT_M / df.box.head(1).item()[3]
        df.index = pd.to_datetime(df.index, unit='ms')
        df['y'] = df.box.apply(lambda r: - r[1] * m_to_p_ratio)
        interpolated = df.y.resample('1L').interpolate()
        smoothed = interpolated.ewm(span=.5*INTERPOLATION_SPAN).mean()
        velocity = (smoothed.diff() * MILLI).ewm(span=INTERPOLATION_SPAN).mean()
        acceleration = (velocity.diff() * MILLI).ewm(span=INTERPOLATION_SPAN).mean()

        person_height = m_to_p_ratio * df.box[-1][-1]

        df = pd.DataFrame({
            'y': smoothed,
            'v': velocity,
            'a': acceleration.shift(-20)
        })
        df['freefall'] = ((df.a + EARTH_GRAVITY).abs() < ACCELERATION_ERROR)
        df['local_maximum'] = ((df.y.shift(1) < df.y) & (df.y.shift(-1) <= df.y))
        df['high_enough'] = (df.y - df.y.min()) > person_height * 0.1

        if any(df.freefall & df.local_maximum & df.high_enough):
            self._boxes = self._boxes[-MIN_N_FRAMES:]
            self._timestamps = self._timestamps[-MIN_N_FRAMES:]
            return True

        return False

    def count_jumps(self, box, timestamp):
        if box is None:
            return self._count

        if self._is_height_change(box):
            self._timestamps = []
            self._boxes = []
            self._all_timestamps = []
            self._all_boxes = []
            self._count = 0
            self._last_jump_timestamp = None

        self._boxes.append(box)
        self._timestamps.append(timestamp)
        self._all_boxes.append(box)
        self._all_timestamps.append(timestamp)

        if len(self._boxes) < MIN_N_FRAMES:
            return self._count

        if len(self._boxes) > 4 * INTERPOLATION_SPAN:
            self._boxes = self._boxes[:INTERPOLATION_SPAN]
            self._timestamps = self._timestamps[:INTERPOLATION_SPAN]

        if self._check_for_jump():
            if self._last_jump_timestamp and timestamp - self._last_jump_timestamp > MAX_MILLISECONDS_BETWEEN_JUMPS:
                self._count = 0

            self._count += 1
            self._last_jump_timestamp = timestamp

        return self._count

    @property
    def df(self):
        return pd.DataFrame({
            'box': self._boxes
        }, index=self._timestamps)

    @property
    def all_df(self):
        return pd.DataFrame({
            'box': self._all_boxes
        }, index=self._all_timestamps)

    def dump(self):
        self.all_df.to_pickle('boxes_2.df')

    def __del__(self):
        self.dump()
        pass
