require('dotenv').config();
const fs = require('fs');
const path = require('path');
const express = require('express');
const session = require('express-session');
const SQLiteStore = require('connect-sqlite3')(session);
const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const methodOverride = require('method-override');

const app = express();
const PORT = process.env.PORT || 3000;
const PLATFORM_COMMISSION_RATE = Number(process.env.PLATFORM_COMMISSION_RATE || 0.2);

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
fs.mkdirSync(DATA_DIR, { recursive: true });

const dbPath = path.join(DATA_DIR, 'app.db');
const db = new Database(dbPath);
db.pragma('journal_mode = WAL');

function migrate() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('student','instructor','admin')),
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS courses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      instructor_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      category TEXT NOT NULL,
      description TEXT NOT NULL,
      level TEXT NOT NULL,
      price_cents INTEGER NOT NULL,
      thumbnail_url TEXT,
      published INTEGER NOT NULL DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (instructor_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS lessons (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      content TEXT NOT NULL,
      position INTEGER NOT NULL,
      FOREIGN KEY (course_id) REFERENCES courses(id)
    );

    CREATE TABLE IF NOT EXISTS purchases (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      student_id INTEGER NOT NULL,
      amount_cents INTEGER NOT NULL,
      platform_fee_cents INTEGER NOT NULL,
      instructor_earnings_cents INTEGER NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (course_id) REFERENCES courses(id),
      FOREIGN KEY (student_id) REFERENCES users(id),
      UNIQUE(course_id, student_id)
    );
  `);

  const adminEmail = process.env.ADMIN_EMAIL || 'admin@beauty.local';
  const exists = db.prepare('SELECT id FROM users WHERE email = ?').get(adminEmail);
  if (!exists) {
    const hash = bcrypt.hashSync(process.env.ADMIN_PASSWORD || 'admin123', 10);
    db.prepare('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)').run(
      'Platform Admin',
      adminEmail,
      hash,
      'admin'
    );
  }
}

migrate();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(methodOverride('_method'));
app.use(
  session({
    store: new SQLiteStore({ db: 'sessions.db', dir: DATA_DIR }),
    secret: process.env.SESSION_SECRET || 'dev-secret',
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 1000 * 60 * 60 * 24 * 7 }
  })
);

app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  res.locals.formatMoney = (cents) => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }).format(cents / 100);
  res.locals.commissionPercent = Math.round(PLATFORM_COMMISSION_RATE * 100);
  next();
});

const requireAuth = (req, res, next) => (req.session.user ? next() : res.redirect('/login'));
const requireRole = (...roles) => (req, res, next) => (req.session.user && roles.includes(req.session.user.role) ? next() : res.status(403).send('Доступ запрещен'));

app.get('/', (req, res) => {
  const courses = db
    .prepare(
      `SELECT c.*, u.name AS instructor_name,
       (SELECT COUNT(*) FROM purchases p WHERE p.course_id = c.id) as sales_count
       FROM courses c
       JOIN users u ON u.id = c.instructor_id
       WHERE c.published = 1
       ORDER BY c.created_at DESC`
    )
    .all();
  res.render('home', { courses });
});

app.get('/register', (req, res) => res.render('register', { error: null }));
app.post('/register', (req, res) => {
  const { name, email, password, role } = req.body;
  if (!name || !email || !password || !['student', 'instructor'].includes(role)) {
    return res.status(400).render('register', { error: 'Заполните все поля корректно.' });
  }
  try {
    const hash = bcrypt.hashSync(password, 10);
    const result = db.prepare('INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)').run(name, email.toLowerCase(), hash, role);
    req.session.user = { id: result.lastInsertRowid, name, email, role };
    res.redirect('/dashboard');
  } catch {
    res.status(400).render('register', { error: 'Email уже используется.' });
  }
});

app.get('/login', (req, res) => res.render('login', { error: null }));
app.post('/login', (req, res) => {
  const { email, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE email = ?').get((email || '').toLowerCase());
  if (!user || !bcrypt.compareSync(password || '', user.password_hash)) {
    return res.status(400).render('login', { error: 'Неверные данные входа.' });
  }
  req.session.user = { id: user.id, name: user.name, email: user.email, role: user.role };
  res.redirect('/dashboard');
});

app.post('/logout', (req, res) => req.session.destroy(() => res.redirect('/')));

app.get('/dashboard', requireAuth, (req, res) => {
  if (req.session.user.role === 'instructor') {
    const courses = db.prepare('SELECT * FROM courses WHERE instructor_id = ? ORDER BY created_at DESC').all(req.session.user.id);
    const stats = db
      .prepare(
        `SELECT 
           COALESCE(SUM(p.amount_cents),0) AS gross,
           COALESCE(SUM(p.platform_fee_cents),0) AS platform,
           COALESCE(SUM(p.instructor_earnings_cents),0) AS payout
         FROM purchases p
         JOIN courses c ON c.id = p.course_id
         WHERE c.instructor_id = ?`
      )
      .get(req.session.user.id);
    return res.render('dashboard_instructor', { courses, stats });
  }

  if (req.session.user.role === 'admin') {
    const stats = db
      .prepare(
        `SELECT 
          COALESCE(SUM(amount_cents),0) as gross,
          COALESCE(SUM(platform_fee_cents),0) as commission,
          COUNT(*) as sales
         FROM purchases`
      )
      .get();
    const topCourses = db
      .prepare(
        `SELECT c.title, COUNT(p.id) as sales, COALESCE(SUM(p.amount_cents),0) as revenue
         FROM courses c
         LEFT JOIN purchases p ON p.course_id = c.id
         GROUP BY c.id
         ORDER BY revenue DESC
         LIMIT 10`
      )
      .all();
    return res.render('dashboard_admin', { stats, topCourses });
  }

  const myCourses = db
    .prepare(
      `SELECT c.*, u.name AS instructor_name, p.created_at as purchase_date
      FROM purchases p
      JOIN courses c ON c.id = p.course_id
      JOIN users u ON u.id = c.instructor_id
      WHERE p.student_id = ?
      ORDER BY p.created_at DESC`
    )
    .all(req.session.user.id);

  res.render('dashboard_student', { myCourses });
});

app.get('/courses/new', requireAuth, requireRole('instructor'), (req, res) => res.render('course_new', { error: null }));
app.post('/courses', requireAuth, requireRole('instructor'), (req, res) => {
  const { title, category, description, level, price, thumbnail_url } = req.body;
  if (!title || !category || !description || !level || !price) {
    return res.status(400).render('course_new', { error: 'Заполните обязательные поля.' });
  }
  const priceCents = Math.round(Number(price) * 100);
  if (!Number.isFinite(priceCents) || priceCents < 100) {
    return res.status(400).render('course_new', { error: 'Минимальная цена 1 RUB.' });
  }

  const result = db
    .prepare(
      `INSERT INTO courses (instructor_id,title,category,description,level,price_cents,thumbnail_url,published)
       VALUES (?,?,?,?,?,?,?,?)`
    )
    .run(req.session.user.id, title, category, description, level, priceCents, thumbnail_url || '', 1);

  db.prepare('INSERT INTO lessons (course_id,title,content,position) VALUES (?,?,?,?)').run(
    result.lastInsertRowid,
    'Вводный урок',
    'Добро пожаловать на курс! Здесь будет ваша программа обучения.',
    1
  );

  res.redirect('/dashboard');
});

app.get('/courses/:id', (req, res) => {
  const course = db
    .prepare(
      `SELECT c.*, u.name as instructor_name
       FROM courses c JOIN users u ON u.id = c.instructor_id
       WHERE c.id = ? AND c.published = 1`
    )
    .get(req.params.id);

  if (!course) return res.status(404).send('Курс не найден');

  const lessons = db.prepare('SELECT * FROM lessons WHERE course_id = ? ORDER BY position').all(course.id);
  let purchased = false;
  if (req.session.user && req.session.user.role === 'student') {
    purchased = !!db.prepare('SELECT id FROM purchases WHERE course_id = ? AND student_id = ?').get(course.id, req.session.user.id);
  }
  const platformFeeCents = Math.round(course.price_cents * PLATFORM_COMMISSION_RATE);
  const instructorEarningsCents = course.price_cents - platformFeeCents;

  res.render('course_show', { course, lessons, purchased, platformFeeCents, instructorEarningsCents });
});

app.post('/courses/:id/purchase', requireAuth, requireRole('student'), (req, res) => {
  const course = db.prepare('SELECT * FROM courses WHERE id = ? AND published = 1').get(req.params.id);
  if (!course) return res.status(404).send('Курс не найден');

  const exists = db.prepare('SELECT id FROM purchases WHERE course_id = ? AND student_id = ?').get(course.id, req.session.user.id);
  if (exists) return res.redirect(`/courses/${course.id}`);

  const platformFeeCents = Math.round(course.price_cents * PLATFORM_COMMISSION_RATE);
  const instructorEarningsCents = course.price_cents - platformFeeCents;

  db.prepare(
    `INSERT INTO purchases (course_id, student_id, amount_cents, platform_fee_cents, instructor_earnings_cents)
     VALUES (?, ?, ?, ?, ?)`
  ).run(course.id, req.session.user.id, course.price_cents, platformFeeCents, instructorEarningsCents);

  res.redirect('/dashboard');
});

app.delete('/courses/:id', requireAuth, requireRole('instructor', 'admin'), (req, res) => {
  const course = db.prepare('SELECT * FROM courses WHERE id = ?').get(req.params.id);
  if (!course) return res.redirect('/dashboard');
  if (req.session.user.role === 'instructor' && course.instructor_id !== req.session.user.id) {
    return res.status(403).send('Нельзя удалить чужой курс');
  }

  db.prepare('DELETE FROM lessons WHERE course_id = ?').run(course.id);
  db.prepare('DELETE FROM purchases WHERE course_id = ?').run(course.id);
  db.prepare('DELETE FROM courses WHERE id = ?').run(course.id);
  res.redirect('/dashboard');
});

app.listen(PORT, () => {
  console.log(`Beauty Academy запущен: http://localhost:${PORT}`);
});
