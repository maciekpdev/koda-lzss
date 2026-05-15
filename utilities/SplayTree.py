class SplayNode:
    _slots_ = ('position', 'left', 'right', 'parent')

    def __init__(self, position: int):
        self.position = position
        self.left = None
        self.right = None
        self.parent = None

class SplayTree:
    def __init__(self, data: bytes, lookahead_size: int):
        self.data = data
        self.lookahead_size = lookahead_size
        self.root = None
        self.node_map: dict[int, SplayNode] = {}

    def _compare_at(self, pos1: int, pos2: int) -> tuple[int, int]:
        max_len = min(self.lookahead_size, len(self.data) - pos1, len(self.data) - pos2)
        for i in range(max_len):
            if self.data[pos1 + i] < self.data[pos2 + i]:
                return -1, i
            elif self.data[pos1 + i] > self.data[pos2 + i]:
                return 1, i
        return 0, max_len

    def _rotate_left(self, node: SplayNode) -> None:
        r = node.right
        node.right = r.left
        if r.left:
            r.left.parent = node
        r.parent = node.parent
        if not node.parent:
            self.root = r
        elif node is node.parent.left:
            node.parent.left = r
        else:
            node.parent.right = r
        r.left = node
        node.parent = r

    def _rotate_right(self, node: SplayNode) -> None:
        l = node.left
        node.left = l.right
        if l.right:
            l.right.parent = node
        l.parent = node.parent
        if not node.parent:
            self.root = l
        elif node is node.parent.right:
            node.parent.right = l
        else:
            node.parent.left = l
        l.right = node
        node.parent = l

    def _splay(self, node: SplayNode) -> None:
        while node.parent:
            p = node.parent
            g = p.parent
            if not g:
                if node is p.left:
                    self._rotate_right(p)
                else:
                    self._rotate_left(p)
            elif (node is p.left) == (p is g.left):
                # Zig-zig
                if node is p.left:
                    self._rotate_right(g)
                    self._rotate_right(p)
                else:
                    self._rotate_left(g)
                    self._rotate_left(p)
            else:
                # Zig-zag
                if node is p.right:
                    self._rotate_left(p)
                    self._rotate_right(g)
                else:
                    self._rotate_right(p)
                    self._rotate_left(g)

    def insert(self, position: int) -> SplayNode:
        node = SplayNode(position)
        self.node_map[position] = node

        if not self.root:
            self.root = node
            return node

        current = self.root
        while True:
            cmp, _ = self._compare_at(position, current.position)
            if cmp <= 0:
                if not current.left:
                    current.left = node
                    node.parent = current
                    break
                current = current.left
            else:
                if not current.right:
                    current.right = node
                    node.parent = current
                    break
                current = current.right

        self._splay(node)
        return node

    def delete(self, position: int) -> bool:
        node = self.node_map.pop(position, None)
        if node is None:
            return False
        self._delete_node(node)
        return True

    def _delete_node(self, node: SplayNode) -> None:
        self._splay(node)

        if not node.left:
            self.root = node.right
            if self.root:
                self.root.parent = None
        elif not node.right:
            self.root = node.left
            if self.root:
                self.root.parent = None
        else:
            left = node.left
            right = node.right
            left.parent = None
            right.parent = None

            # Find max in left subtree
            m = left
            while m.right:
                m = m.right
            self._splay(m)

            # m is now root of left subtree with no right child
            m.right = right
            right.parent = m
            self.root = m

        node.left = None
        node.right = None
        node.parent = None

    def find_best_match(self, current_pos: int, max_offset: int) -> tuple[int, int]:
        best_offset = 0
        best_length = 0
        last_visited = None

        current = self.root
        while current:
            last_visited = current
            pos = current.position
            offset = current_pos - pos

            cmp, match_len = self._compare_at(current_pos, pos)

            if 0 < offset <= max_offset and match_len > best_length:
                best_length = match_len
                best_offset = offset

            if best_length == self.lookahead_size:
                break

            if cmp <= 0:
                current = current.left
            else:
                current = current.right

        if last_visited:
            self._splay(last_visited)

        return best_offset, best_length

    def clear(self) -> None:
        self.root = None
        self.node_map.clear()
