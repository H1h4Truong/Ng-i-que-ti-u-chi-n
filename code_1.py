import pygame
import os

# --- Lớp Character (Nhân vật) để quản lý animation và trạng thái ---
class Character(pygame.sprite.Sprite):
    def __init__(self, anim_config, initial_position, scale_factor, is_flipped=False, owner_type="player", max_hp=250):
        super().__init__()

        self.animations = {}
        self.fps_settings = {}
        self.current_animation_name = ""
        self.current_frame_index = 0
        self.last_frame_update_time = pygame.time.get_ticks()

        self.scale_factor = scale_factor
        self.is_flipped = is_flipped
        self.x, self.y = initial_position
        self.original_x = initial_position[0]
        self.original_y = initial_position[1]

        self.hit_image = None
        self.is_showing_hit = False
        self.hit_display_duration = 500
        self.hit_start_time = 0

        self.is_defending = False
        self.defend_image = None
        self.is_attacking = False # Cờ để biết nhân vật có đang trong trạng thái gây sát thương không

        self.owner_type = owner_type

        # --- Thuộc tính máu mới ---
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.is_alive = True # Trạng thái sống/chết

        # --- Thuộc tính hồi máu mới ---
        self.healing_amount = 2.5
        self.healing_interval = 5000 # 5 giây = 5000 mili giây
        self.last_heal_time = pygame.time.get_ticks() # Thời điểm hồi máu gần nhất

        # --- Thuộc tính Cooldown mới ---
        self.attack_cooldown = 500 # 0.5 giây = 500 mili giây
        self.last_attack_time = 0 # Thời điểm tấn công gần nhất

        # --- Thuộc tính Hitbox Enemy (đã điều chỉnh, vẫn giữ lại cho mục đích hình ảnh) ---
        self.enemy_attack_offset = 70
        self.enemy_attack_range = 80
        self.enemy_attack_hitbox_multiplier = 1.8 

        self._load_animations(anim_config)

        if self.owner_type == "player" and "defend_static" in self.animations:
            if self.animations["defend_static"]:
                self.defend_image = self.animations["defend_static"][0]
        elif self.owner_type == "enemy" and "enemy_defend_static" in self.animations:
            if self.animations["enemy_defend_static"]:
                self.defend_image = self.animations["enemy_defend_static"][0]

        if "idle" in self.animations:
            self.set_animation("idle")
        elif self.animations:
            self.set_animation(list(self.animations.keys())[0])
        else:
            print(f"Cảnh báo: Nhân vật tại {initial_position} không có animation nào được tải.")
            self.image = pygame.Surface((50, 50), pygame.SRCALPHA)
            self.image.fill((255, 0, 0, 100))
            self.rect = self.image.get_rect(topleft=initial_position)
            return

        self.image = self.animations[self.current_animation_name][self.current_frame_index]
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

        self.action_state = "idle"
        self.dash_speed = 20 
        self.dash_target_x = 0
        self.dash_start_x = 0
        self.dash_sequence = []

        # Thêm thuộc tính để lưu trữ đối tượng đối thủ
        self.opponent = None 

        # Thêm cờ để kiểm tra xem phím phòng thủ có đang được giữ hay không
        self.is_defend_key_held = False 

    def _load_animations(self, anim_config):
        for anim_name, config in anim_config.items():
            path = config["path"]
            fps = config.get("fps", 10)
            self.fps_settings[anim_name] = fps

            frames = []
            if os.path.isdir(path):
                image_filenames = sorted([f for f in os.listdir(path)
                                         if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))])

                if not image_filenames:
                    print(f"Không tìm thấy tệp hình ảnh nào trong thư mục '{path}' cho '{anim_name}'.")
                    continue

                for filename in image_filenames:
                    full_path = os.path.join(path, filename)
                    try:
                        img = pygame.image.load(full_path).convert_alpha()
                        new_width = int(img.get_width() * self.scale_factor)
                        new_height = int(img.get_height() * self.scale_factor)
                        img = pygame.transform.scale(img, (new_width, new_height))
                        if self.is_flipped:
                            img = pygame.transform.flip(img, True, False)
                        frames.append(img)
                    except pygame.error as e:
                        print(f"Lỗi khi tải hoặc xử lý khung hình {full_path}: {e}")
                        continue
                self.animations[anim_name] = frames
            elif os.path.isfile(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    new_width = int(img.get_width() * self.scale_factor)
                    new_height = int(img.get_height() * self.scale_factor)
                    img = pygame.transform.scale(img, (new_width, new_height))
                    if self.is_flipped:
                        img = pygame.transform.flip(img, True, False)

                    if anim_name == "hit_static":
                        self.hit_image = img
                    elif anim_name == "defend_static" or anim_name == "enemy_defend_static":
                        frames.append(img)
                        self.animations[anim_name] = frames
                    else:
                        frames.append(img)
                        self.animations[anim_name] = frames
                except pygame.error as e:
                    print(f"Lỗi khi tải hoặc xử lý tệp hình ảnh {path} cho '{anim_name}': {e}")
                else:
                    print(f"Lỗi: Đường dẫn '{path}' cho '{anim_name}' không phải là thư mục cũng không phải tệp hình ảnh hợp lệ.")

    def set_animation(self, anim_name, force_restart=False):
        # Không thay đổi animation nếu đang hit hoặc đã chết
        if self.is_showing_hit or not self.is_alive:
            return
        
        # Nếu đang phòng thủ và phím phòng thủ vẫn đang giữ, không thay đổi animation
        if self.is_defending and self.is_defend_key_held:
            return

        if anim_name not in self.animations:
            print(f"Cảnh báo: Animation '{anim_name}' không tồn tại.")
            return

        if self.current_animation_name != anim_name or force_restart:
            self.current_animation_name = anim_name
            self.current_frame_index = 0
            self.last_frame_update_time = pygame.time.get_ticks()
            self.image = self.animations[self.current_animation_name][self.current_frame_index]
            self.rect = self.image.get_rect(topleft=(self.x, self.y))

    def update_animation(self):
        if not self.is_alive: # Không cập nhật animation nếu đã chết
            return

        if self.is_showing_hit:
            current_time = pygame.time.get_ticks()
            if current_time - self.hit_start_time > self.hit_display_duration:
                self.is_showing_hit = False
                self.action_state = "idle"
                self.x = self.original_x
                self.y = self.original_y
                self.rect.topleft = (self.x, self.y)
                self.set_animation("idle")
            return

        # Nếu đang phòng thủ và phím phòng thủ đang giữ, không cập nhật animation khác
        if self.is_defending and self.is_defend_key_held:
            return

        current_time = pygame.time.get_ticks()
        current_fps = self.fps_settings.get(self.current_animation_name, 10)
        frame_duration_ms = 1000 / current_fps

        if current_time - self.last_frame_update_time > frame_duration_ms:
            self.current_frame_index += 1
            num_frames = len(self.animations[self.current_animation_name])

            if self.current_frame_index >= num_frames:
                # Đảm bảo animation tấn công dừng ở khung cuối cùng và sau đó chuyển về idle
                if self.current_animation_name in ["attack", "enemy_attack"]:
                    self.current_frame_index = num_frames - 1 # Giữ ở khung cuối cùng
                    self._action_complete_attack() # Xử lý hoàn thành tấn công
                else:
                    self.current_frame_index = 0

            self.image = self.animations[self.current_animation_name][self.current_frame_index]
            self.rect = self.image.get_rect(topleft=(self.x, self.y))

            # --- ĐIỀU CHỈNH HITBOX CHO ANIMATION TẤN CÔNG (khi is_attacking là True) ---
            # Vẫn giữ lại để hình ảnh hitbox trông đúng, nhưng sát thương đã được xử lý ở start_attack_direct
            if self.is_attacking:
                if self.owner_type == "player" and self.current_animation_name == "attack":
                    offset_x_player = 50
                    new_width_player = 100

                    if not self.is_flipped:
                        self.rect.x = self.x - offset_x_player
                        self.rect.width = self.image.get_width() + new_width_player
                    else:
                        self.rect.x = self.x
                        self.rect.width = self.image.get_width() + new_width_player

                elif self.owner_type == "enemy" and self.current_animation_name == "enemy_attack":
                    offset_x = self.enemy_attack_offset
                    attack_width = int(self.enemy_attack_range * self.enemy_attack_hitbox_multiplier)

                    if self.is_flipped: 
                        self.rect.right = self.x + self.image.get_width() - offset_x
                        self.rect.width = attack_width
                        self.rect.x = self.rect.right - self.rect.width 
                    else: 
                        self.rect.x = self.x + offset_x
                        self.rect.width = attack_width
            else:
                self.rect = self.image.get_rect(topleft=(self.x, self.y))

            self.last_frame_update_time = current_time

    # --- Phương thức xử lý hoàn thành tấn công ---
    def _action_complete_attack(self):
        self.is_attacking = False
        self.last_attack_time = pygame.time.get_ticks() # Đặt thời gian cooldown khi kết thúc tấn công
        self.action_state = "idle"
        self.set_animation("idle")
        print(f"DEBUG: {self.owner_type} kết thúc tấn công. is_attacking = {self.is_attacking}")

    # --- Phương thức tấn công trực tiếp cho Player và Enemy ---
    def start_attack_direct(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_attack_time < self.attack_cooldown:
            # print(f"DEBUG: {self.owner_type} đang trong cooldown tấn công.")
            return

        if self.action_state == "idle" and not self.is_defending and not self.is_showing_hit and self.is_alive:
            self.set_animation("attack" if self.owner_type == "player" else "enemy_attack", force_restart=True)
            self.action_state = "attacking" if self.owner_type == "player" else "enemy_attacking"
            self.is_attacking = True
            
            # --- LOGIC TRỪ HP NGAY LẬP TỨC KHI TẤN CÔNG KHỞI TẠO ---
            if self.opponent and self.opponent.is_alive:
                if self.opponent.is_defending:
                    damage_to_deal = 0  # Chặn hoàn toàn sát thương khi phòng thủ
                    print(f"DEBUG: {self.owner_type} tấn công. {self.opponent.owner_type} đang phòng thủ. Không gây sát thương.")
                    self.opponent.take_damage(damage_to_deal)
                    # KHÔNG GỌI stop_defend() NẾU PHÍM PHÒNG THỦ ĐANG ĐƯỢC GIỮ
                    # self.opponent.stop_defend() # Dừng phòng thủ sau khi nhận hit
                else:
                    damage_to_deal = 25
                    print(f"DEBUG: {self.owner_type} tấn công. {self.opponent.owner_type} không phòng thủ. Gây {damage_to_deal} sát thương.")
                    self.opponent.take_damage(damage_to_deal)
                    # Nếu không phòng thủ, hiển thị hit_image
                    if self.opponent.is_alive and self.opponent.hit_image:
                        self.opponent.is_showing_hit = True
                        self.opponent.action_state = "hit"
                        self.opponent.hit_start_time = pygame.time.get_ticks()
                        self.opponent.image = self.opponent.hit_image
                        self.opponent.rect = self.opponent.image.get_rect(topleft=(self.opponent.x, self.opponent.y))
                    else:
                        self.opponent.action_state = "idle" # Nếu chết hoặc không có hit_image, về idle
                        self.opponent.set_animation("idle")


            print(f"DEBUG: {self.owner_type} bắt đầu tấn công trực tiếp. is_attacking = {self.is_attacking}")
        else:
            print(f"DEBUG: {self.owner_type} không thể tấn công: action_state={self.action_state}, defending={self.is_defending}, alive={self.is_alive}")

    # --- Phương thức phòng thủ mới ---
    def start_defend(self):
        if self.action_state == "idle" and not self.is_showing_hit and self.is_alive:
            self.is_defending = True
            self.is_defend_key_held = True # Đặt cờ là phím phòng thủ đang được giữ
            self.action_state = "defending"
            print(f"DEBUG: {self.owner_type} BẮT ĐẦU phòng thủ. is_defending = {self.is_defending}")
            if self.owner_type == "player" and "defend_static" in self.animations and self.animations["defend_static"]:
                self.image = self.animations["defend_static"][0]
            elif self.owner_type == "enemy" and "enemy_defend_static" in self.animations and self.animations["enemy_defend_static"]:
                self.image = self.animations["enemy_defend_static"][0]
            else:
                print(f"Cảnh báo: Không tìm thấy ảnh phòng thủ cho {self.owner_type}.")

            self.rect = self.image.get_rect(topleft=(self.x, self.y))

    def stop_defend(self):
        self.is_defend_key_held = False # Bỏ cờ phím phòng thủ không còn được giữ
        if self.is_defending:
            self.is_defending = False
            self.action_state = "idle"
            print(f"DEBUG: {self.owner_type} DỪNG phòng thủ. is_defending = {self.is_defending}")
            self.set_animation("idle", force_restart=True)

    def update_position(self):
        pass # Không có di chuyển trong chế độ này

    def take_damage(self, damage_amount):
        """Phương thức mới để giảm máu và kiểm tra cái chết."""
        if not self.is_alive:
            return

        self.current_hp -= damage_amount
        if self.current_hp <= 0:
            self.current_hp = 0
            self.is_alive = False
            print(f"DEBUG: {self.owner_type} đã bị đánh bại!")
            self.action_state = "dead" # Thêm trạng thái chết
            self.image = pygame.Surface((50, 50), pygame.SRCALPHA) # Ảnh rỗng hoặc ảnh chết
            self.image.fill((0, 0, 0, 100)) # Làm mờ nhân vật khi chết
            self.rect = self.image.get_rect(topleft=(self.x, self.y)) # Cập nhật rect
        else:
            print(f"DEBUG: {self.owner_type} nhận {damage_amount} sát thương. HP còn lại: {self.current_hp}")


    def draw_health_bar(self, screen, x, y, width, height, border_thickness=2, font_size=16):
        """Vẽ thanh máu của nhân vật và hiển thị số HP."""
        # Màu sắc thanh máu
        if self.owner_type == "player":
            health_color = (255, 165, 0) # Màu cam cho Player
        else:
            health_color = (255, 0, 0) # Màu đỏ cho Enemy

        background_color = (50, 50, 50) # Màu nền của thanh máu
        border_color = (0, 0, 0) # Màu viền
        text_color = (255, 255, 255) # Màu chữ

        # Vẽ nền thanh máu
        pygame.draw.rect(screen, background_color, (x, y, width, height))

        # Tính toán chiều rộng của phần máu hiện tại
        health_ratio = self.current_hp / self.max_hp
        current_health_width = int(width * health_ratio)

        # Vẽ phần máu hiện tại
        pygame.draw.rect(screen, health_color, (x, y, current_health_width, height))

        # Vẽ viền
        pygame.draw.rect(screen, border_color, (x, y, width, height), border_thickness)

        # Tạo và vẽ văn bản HP
        font = pygame.font.Font(None, font_size) # Bạn có thể thay đổi font và kích thước
        hp_text = f"HP: {int(self.current_hp)}/{int(self.max_hp)}" # Ép kiểu về int để hiển thị số nguyên
        text_surface = font.render(hp_text, True, text_color)
        
        # Đặt vị trí văn bản ở giữa thanh máu
        text_rect = text_surface.get_rect(center=(x + width // 2, y + height // 2))
        screen.blit(text_surface, text_rect)


    def update(self):
        self.update_animation()
        self.update_position()
        # Logic hồi máu
        if self.is_alive and self.action_state == "idle": # Chỉ hồi máu khi còn sống và ở trạng thái idle
            current_time = pygame.time.get_ticks()
            if current_time - self.last_heal_time > self.healing_interval:
                self.current_hp = min(self.max_hp, self.current_hp + self.healing_amount)
                self.last_heal_time = current_time


def run_game_scene(player_anim_configs, enemy_anim_configs,
                   window_width=650, window_height=650,
                   player_scale=0.8, enemy_scale=0.8):
    pygame.init()

    screen = pygame.display.set_mode((window_width, window_height))
    pygame.display.set_caption("Chém và Sát Thương Tức Thì")

    temp_enemy_img_width = 0
    temp_enemy_img_height = 0
    if "idle" in enemy_anim_configs:
        idle_path = enemy_anim_configs["idle"]["path"]
        if os.path.isdir(idle_path):
            temp_files = sorted([f for f in os.listdir(idle_path) if f.lower().endswith(('.png', '.jpg'))])
            if temp_files:
                try:
                    temp_img = pygame.image.load(os.path.join(idle_path, temp_files[0]))
                    temp_enemy_img_width = int(temp_img.get_width() * enemy_scale)
                    temp_enemy_img_height = int(temp_img.get_height() * enemy_scale)
                except pygame.error:
                    pass
        elif os.path.isfile(idle_path):
            try:
                temp_img = pygame.image.load(idle_path)
                temp_enemy_img_width = int(temp_img.get_width() * enemy_scale)
                temp_enemy_img_height = int(temp_img.get_height() * enemy_scale)
            except pygame.error:
                pass

    enemy_initial_y = (window_height // 2) - (temp_enemy_img_height // 2) if temp_enemy_img_height > 0 else (window_height // 2) - 50
    enemy_initial_x = window_width * 3 // 4 - (temp_enemy_img_width // 2) if temp_enemy_img_width > 0 else window_width * 3 // 4 - 50

    enemy = Character(enemy_anim_configs, (enemy_initial_x, enemy_initial_y), enemy_scale, is_flipped=True, owner_type="enemy")

    temp_player_img_width = 0
    temp_player_img_height = 0
    if "idle" in player_anim_configs:
        idle_path = player_anim_configs["idle"]["path"]
        if os.path.isdir(idle_path):
            temp_files = sorted([f for f in os.listdir(idle_path) if f.lower().endswith(('.png', '.jpg'))])
            if temp_files:
                try:
                    temp_img = pygame.image.load(os.path.join(idle_path, temp_files[0]))
                    temp_player_img_width = int(temp_img.get_width() * player_scale)
                    temp_player_img_height = int(temp_img.get_height() * player_scale)
                except pygame.error:
                    pass
        elif os.path.isfile(idle_path):
            try:
                temp_img = pygame.image.load(idle_path)
                temp_player_img_width = int(temp_img.get_width() * player_scale)
                temp_player_img_height = int(temp_img.get_height() * player_scale)
            except pygame.error:
                pass

    player_initial_y = (window_height // 2) - (temp_player_img_height // 2) if temp_player_img_height > 0 else (window_height // 2) - 50
    player_initial_x = window_width // 4 - (temp_player_img_width // 2) if temp_player_img_width > 0 else window_width // 4 - 50

    player = Character(player_animation_configs, (player_initial_x, player_initial_y), player_scale, owner_type="player")

    # Gán đối thủ cho mỗi nhân vật để họ có thể tương tác sát thương trực tiếp
    player.opponent = enemy
    enemy.opponent = player

    clock = pygame.time.Clock()
    running = True
    background_color = (255, 255, 255)

    print("--- Hướng dẫn điều khiển ---")
    print("Nhấn **W** để nhân vật chính (Player) TẤN CÔNG. (Trừ HP ngay lập tức)")
    print("Nhấn **S** để nhân vật chính (Player) PHÒNG THỦ. (Nhả **S** để dừng phòng thủ)")
    print("Nhấn **Mũi tên LÊN** để kẻ thù (Enemy) TẤN CÔNG. (Trừ HP ngay lập tức)")
    print("Nhấn **Mũi tên XUỐNG** để kẻ thù (Enemy) PHÒNG THỦ. (Nhả **Mũi tên XUỐNG** để dừng phòng thủ)")
    print("Mỗi 5 giây, cả hai nhân vật sẽ hồi 2.5 HP.")
    print("Sau mỗi lần tấn công có cooldown 0.5 giây.")
    print("Khi TẤN CÔNG, đối thủ sẽ mất 25 HP nếu KHÔNG phòng thủ, hoặc 10 HP nếu ĐANG phòng thủ.")
    print("Nhấn **ESC** hoặc đóng cửa sổ để thoát.")
    print("--------------------------")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_w:
                    player.start_attack_direct()
                if event.key == pygame.K_s:
                    if player.is_alive: # Chỉ phòng thủ khi còn sống
                        player.start_defend()
                if event.key == pygame.K_UP:
                    enemy.start_attack_direct()
                if event.key == pygame.K_DOWN:
                    if enemy.is_alive: # Chỉ phòng thủ khi còn sống
                        enemy.start_defend()

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_s:
                    player.stop_defend()
                if event.key == pygame.K_DOWN:
                    enemy.stop_defend()

        # Cập nhật nhân vật chỉ nếu còn sống
        if player.is_alive:
            player.update()
        if enemy.is_alive:
            enemy.update()

        screen.fill(background_color)
        screen.blit(player.image, player.rect)
        screen.blit(enemy.image, enemy.rect)

        # --- Vẽ thanh máu ---
        # Vị trí thanh máu Player (góc trên bên trái)
        player_health_bar_x = 20
        player_health_bar_y = 20
        health_bar_width = 200
        health_bar_height = 20
        player.draw_health_bar(screen, player_health_bar_x, player_health_bar_y, health_bar_width, health_bar_height)

        # Vị trí thanh máu Enemy (góc trên bên phải)
        enemy_health_bar_x = window_width - health_bar_width - 20
        enemy_health_bar_y = 20
        enemy.draw_health_bar(screen, enemy_health_bar_x, enemy_health_bar_y, health_bar_width, health_bar_height)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    print("Cửa sổ đã đóng.")

if __name__ == '__main__':
    base_assets_folder = r'E:\PaRa_BaI_HoC\00_Du_An\Game_nha_lam\Ng_que_dai_chien'
    enemy_assets_folder = os.path.join(base_assets_folder, 'Enemy')
    main_assets_folder = os.path.join(base_assets_folder, 'Main')

    player_animation_configs = {
        "idle": {"path": os.path.join(main_assets_folder, 'Dung'), "fps": 10},
        "attack": {"path": os.path.join(main_assets_folder, 'Chem'), "fps": 12},
        "hit_static": {"path": os.path.join(main_assets_folder, 'hit.png')},
        "defend_static": {"path": os.path.join(main_assets_folder, 'phong_thu.png')}
    }

    enemy_animation_configs = {
        "idle": {"path": os.path.join(enemy_assets_folder, 'Enemy_Dung.png'), "fps": 1},
        "hit_static": {"path": os.path.join(enemy_assets_folder, 'Enemy_hit.png')},
        "enemy_attack": {"path": os.path.join(enemy_assets_folder, 'Chem'), "fps": 12},
        "enemy_defend_static": {"path": os.path.join(enemy_assets_folder, 'enemy_phong_thu.png')}
    }

    window_w = 650
    window_h = 650
    player_scale_factor = 1.5
    enemy_scale_factor = 1.5

    run_game_scene(player_animation_configs, enemy_animation_configs,
                   window_w, window_h,
                   player_scale_factor, enemy_scale_factor)