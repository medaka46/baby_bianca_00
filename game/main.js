// Space Invaders Game
class SpaceInvaders {
    constructor() {
        this.canvas = document.getElementById('gameCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.canvas.width = 800;
        this.canvas.height = 600;
        
        // Game state
        this.gameRunning = false;
        this.score = 0;
        this.lives = 3;
        this.level = 1;
        this.gameOver = false;
        
        // Player
        this.player = {
            x: this.canvas.width / 2 - 25,
            y: this.canvas.height - 60,
            width: 50,
            height: 40,
            speed: 5,
            color: '#00ff00'
        };
        
        // Bullets
        this.playerBullets = [];
        this.enemyBullets = [];
        this.bulletSpeed = 7;
        this.enemyBulletSpeed = 3;
        
        // Enemies
        this.enemies = [];
        this.enemyRows = 5;
        this.enemyCols = 10;
        this.enemySpeed = 1;
        this.enemyDirection = 1;
        this.enemyDropDistance = 40;
        
        // Controls
        this.keys = {};
        this.lastShot = 0;
        this.shootCooldown = 250; // milliseconds
        
        // Bind methods
        this.update = this.update.bind(this);
        this.handleKeyDown = this.handleKeyDown.bind(this);
        this.handleKeyUp = this.handleKeyUp.bind(this);
        
        // Initialize
        this.setupEventListeners();
        this.createEnemies();
        this.gameLoop();
    }
    
    setupEventListeners() {
        document.addEventListener('keydown', this.handleKeyDown);
        document.addEventListener('keyup', this.handleKeyUp);
    }
    
    handleKeyDown(e) {
        this.keys[e.code] = true;
        
        // Start game
        if ((e.code === 'Space' || e.code === 'Enter') && !this.gameRunning && !this.gameOver) {
            this.startGame();
        }
        
        // Restart game
        if ((e.code === 'Space' || e.code === 'Enter') && this.gameOver) {
            this.restartGame();
        }
        
        e.preventDefault();
    }
    
    handleKeyUp(e) {
        this.keys[e.code] = false;
    }
    
    startGame() {
        this.gameRunning = true;
    }
    
    restartGame() {
        this.gameRunning = false;
        this.gameOver = false;
        this.score = 0;
        this.lives = 3;
        this.level = 1;
        this.player.x = this.canvas.width / 2 - 25;
        this.playerBullets = [];
        this.enemyBullets = [];
        this.createEnemies();
    }
    
    createEnemies() {
        this.enemies = [];
        const enemyWidth = 40;
        const enemyHeight = 30;
        const spacing = 20;
        const startX = 50;
        const startY = 50;
        
        for (let row = 0; row < this.enemyRows; row++) {
            for (let col = 0; col < this.enemyCols; col++) {
                this.enemies.push({
                    x: startX + col * (enemyWidth + spacing),
                    y: startY + row * (enemyHeight + spacing),
                    width: enemyWidth,
                    height: enemyHeight,
                    type: row < 2 ? 'fast' : row < 4 ? 'medium' : 'slow',
                    color: row < 2 ? '#ff0000' : row < 4 ? '#ffff00' : '#00ffff',
                    points: row < 2 ? 30 : row < 4 ? 20 : 10
                });
            }
        }
    }
    
    updatePlayer() {
        // Move left
        if (this.keys['ArrowLeft'] || this.keys['KeyA']) {
            this.player.x -= this.player.speed;
            if (this.player.x < 0) this.player.x = 0;
        }
        
        // Move right
        if (this.keys['ArrowRight'] || this.keys['KeyD']) {
            this.player.x += this.player.speed;
            if (this.player.x > this.canvas.width - this.player.width) {
                this.player.x = this.canvas.width - this.player.width;
            }
        }
        
        // Shoot
        if ((this.keys['Space'] || this.keys['ArrowUp'] || this.keys['KeyW']) && 
            Date.now() - this.lastShot > this.shootCooldown) {
            this.playerBullets.push({
                x: this.player.x + this.player.width / 2 - 2,
                y: this.player.y,
                width: 4,
                height: 10,
                color: '#ffffff'
            });
            this.lastShot = Date.now();
        }
    }
    
    updateBullets() {
        // Update player bullets
        for (let i = this.playerBullets.length - 1; i >= 0; i--) {
            this.playerBullets[i].y -= this.bulletSpeed;
            
            // Remove bullets that go off screen
            if (this.playerBullets[i].y < 0) {
                this.playerBullets.splice(i, 1);
            }
        }
        
        // Update enemy bullets
        for (let i = this.enemyBullets.length - 1; i >= 0; i--) {
            this.enemyBullets[i].y += this.enemyBulletSpeed;
            
            // Remove bullets that go off screen
            if (this.enemyBullets[i].y > this.canvas.height) {
                this.enemyBullets.splice(i, 1);
            }
        }
    }
    
    updateEnemies() {
        let moveDown = false;
        
        // Check if enemies hit the edge
        for (let enemy of this.enemies) {
            if ((enemy.x <= 0 && this.enemyDirection === -1) || 
                (enemy.x >= this.canvas.width - enemy.width && this.enemyDirection === 1)) {
                moveDown = true;
                break;
            }
        }
        
        // Move enemies
        for (let enemy of this.enemies) {
            if (moveDown) {
                enemy.y += this.enemyDropDistance;
            } else {
                enemy.x += this.enemySpeed * this.enemyDirection;
            }
        }
        
        if (moveDown) {
            this.enemyDirection *= -1;
        }
        
        // Enemy shooting
        if (Math.random() < 0.005 && this.enemies.length > 0) {
            const randomEnemy = this.enemies[Math.floor(Math.random() * this.enemies.length)];
            this.enemyBullets.push({
                x: randomEnemy.x + randomEnemy.width / 2 - 2,
                y: randomEnemy.y + randomEnemy.height,
                width: 4,
                height: 10,
                color: '#ff0000'
            });
        }
    }
    
    checkCollisions() {
        // Player bullets vs enemies
        for (let i = this.playerBullets.length - 1; i >= 0; i--) {
            for (let j = this.enemies.length - 1; j >= 0; j--) {
                if (this.isColliding(this.playerBullets[i], this.enemies[j])) {
                    this.score += this.enemies[j].points;
                    this.playerBullets.splice(i, 1);
                    this.enemies.splice(j, 1);
                    break;
                }
            }
        }
        
        // Enemy bullets vs player
        for (let i = this.enemyBullets.length - 1; i >= 0; i--) {
            if (this.isColliding(this.enemyBullets[i], this.player)) {
                this.enemyBullets.splice(i, 1);
                this.lives--;
                
                if (this.lives <= 0) {
                    this.gameOver = true;
                    this.gameRunning = false;
                }
                break;
            }
        }
        
        // Enemies vs player (game over)
        for (let enemy of this.enemies) {
            if (enemy.y + enemy.height >= this.player.y) {
                this.gameOver = true;
                this.gameRunning = false;
                break;
            }
        }
    }
    
    isColliding(rect1, rect2) {
        return rect1.x < rect2.x + rect2.width &&
               rect1.x + rect1.width > rect2.x &&
               rect1.y < rect2.y + rect2.height &&
               rect1.y + rect1.height > rect2.y;
    }
    
    checkLevelComplete() {
        if (this.enemies.length === 0) {
            this.level++;
            this.createEnemies();
            this.enemySpeed += 0.5;
            this.playerBullets = [];
            this.enemyBullets = [];
        }
    }
    
    drawPlayer() {
        this.ctx.fillStyle = this.player.color;
        this.ctx.fillRect(this.player.x, this.player.y, this.player.width, this.player.height);
        
        // Draw player as a simple spaceship shape
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillRect(this.player.x + 20, this.player.y - 5, 10, 15);
    }
    
    drawEnemies() {
        for (let enemy of this.enemies) {
            this.ctx.fillStyle = enemy.color;
            this.ctx.fillRect(enemy.x, enemy.y, enemy.width, enemy.height);
            
            // Draw simple enemy shape
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fillRect(enemy.x + 5, enemy.y + 5, enemy.width - 10, enemy.height - 10);
        }
    }
    
    drawBullets() {
        // Draw player bullets
        this.ctx.fillStyle = '#ffffff';
        for (let bullet of this.playerBullets) {
            this.ctx.fillRect(bullet.x, bullet.y, bullet.width, bullet.height);
        }
        
        // Draw enemy bullets
        this.ctx.fillStyle = '#ff0000';
        for (let bullet of this.enemyBullets) {
            this.ctx.fillRect(bullet.x, bullet.y, bullet.width, bullet.height);
        }
    }
    
    drawUI() {
        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = '20px Arial';
        this.ctx.fillText(`Score: ${this.score}`, 10, 30);
        this.ctx.fillText(`Lives: ${this.lives}`, 10, 60);
        this.ctx.fillText(`Level: ${this.level}`, 10, 90);
        
        if (!this.gameRunning && !this.gameOver) {
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = '30px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('SPACE INVADERS', this.canvas.width / 2, this.canvas.height / 2 - 100);
            this.ctx.font = '20px Arial';
            this.ctx.fillText('Press SPACE or ENTER to start', this.canvas.width / 2, this.canvas.height / 2 - 50);
            this.ctx.fillText('Use ARROW KEYS or WASD to move', this.canvas.width / 2, this.canvas.height / 2 - 20);
            this.ctx.fillText('Press SPACE or UP ARROW to shoot', this.canvas.width / 2, this.canvas.height / 2 + 10);
            this.ctx.textAlign = 'left';
        }
        
        if (this.gameOver) {
            this.ctx.fillStyle = '#ff0000';
            this.ctx.font = '40px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('GAME OVER', this.canvas.width / 2, this.canvas.height / 2 - 50);
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = '20px Arial';
            this.ctx.fillText(`Final Score: ${this.score}`, this.canvas.width / 2, this.canvas.height / 2);
            this.ctx.fillText('Press SPACE or ENTER to restart', this.canvas.width / 2, this.canvas.height / 2 + 40);
            this.ctx.textAlign = 'left';
        }
    }
    
    update() {
        if (this.gameRunning) {
            this.updatePlayer();
            this.updateBullets();
            this.updateEnemies();
            this.checkCollisions();
            this.checkLevelComplete();
        }
    }
    
    draw() {
        // Clear canvas
        this.ctx.fillStyle = '#000000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        if (this.gameRunning) {
            this.drawPlayer();
            this.drawEnemies();
            this.drawBullets();
        }
        
        this.drawUI();
    }
    
    gameLoop() {
        this.update();
        this.draw();
        requestAnimationFrame(this.gameLoop.bind(this));
    }
}

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Create canvas if it doesn't exist
    if (!document.getElementById('gameCanvas')) {
        const canvas = document.createElement('canvas');
        canvas.id = 'gameCanvas';
        canvas.style.border = '2px solid #ffffff';
        canvas.style.backgroundColor = '#000000';
        canvas.style.display = 'block';
        canvas.style.margin = '20px auto';
        document.body.appendChild(canvas);
    }
    
    // Start the game
    new SpaceInvaders();
}); 