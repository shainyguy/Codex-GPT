require('dotenv').config();
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const express = require('express');
const session = require('express-session');
const SQLiteStore = require('connect-sqlite3')(session);
const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const methodOverride = require('method-override');

const app = express();
const PORT = Number(process.env.PORT || 3000);
const PLATFORM_COMMISSION_RATE = Number(process.env.PLATFORM_COMMISSION_RATE || 0.2);
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const YOOKASSA_SHOP_ID = process.env.YOOKASSA_SHOP_ID || '';
const YOOKASSA_SECRET_KEY = process.env.YOOKASSA_SECRET_KEY || '';

fs.mkdirSync(DATA_DIR, { recursive: true });
const db = new Database(path.join(DATA_DIR, 'app.db'));
db.pragma('journal_mode = WAL');

const categoryOptions = ['Макияж', 'Волосы', 'Ногти', 'Брови', 'Кожа', 'Барбер'];
const levelOptions = ['Начинающий', 'Средний', 'Профи'];
const languageOptions = ['Русский', 'English'];

function migrate() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('student','instructor','admin')),
      specialization TEXT DEFAULT '',
      experience_years INTEGER DEFAULT 0,
      certificates TEXT DEFAULT '',
      portfolio_text TEXT DEFAULT '',
      social_instagram TEXT DEFAULT '',
      social_telegram TEXT DEFAULT '',
      rating REAL DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS courses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      instructor_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      category TEXT NOT NULL,
      description TEXT NOT NULL,
      level TEXT NOT NULL,
      language TEXT NOT NULL DEFAULT 'Русский',
      duration_hours INTEGER NOT NULL DEFAULT 1,
      price_cents INTEGER NOT NULL,
      thumbnail_url TEXT,
      published INTEGER NOT NULL DEFAULT 1,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (instructor_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS modules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      position INTEGER NOT NULL,
      FOREIGN KEY (course_id) REFERENCES courses(id)
    );

    CREATE TABLE IF NOT EXISTS lessons (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      module_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      video_url TEXT DEFAULT '',
      text_content TEXT DEFAULT '',
      position INTEGER NOT NULL,
      duration_min INTEGER DEFAULT 5,
      FOREIGN KEY (module_id) REFERENCES modules(id)
    );

    CREATE TABLE IF NOT EXISTS materials (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('pdf','text')),
      content_url TEXT DEFAULT '',
      content_text TEXT DEFAULT '',
      FOREIGN KEY (course_id) REFERENCES courses(id)
    );

    CREATE TABLE IF NOT EXISTS homework_tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lesson_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      instructions TEXT NOT NULL,
      FOREIGN KEY (lesson_id) REFERENCES lessons(id)
    );

    CREATE TABLE IF NOT EXISTS homework_submissions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      homework_task_id INTEGER NOT NULL,
      student_id INTEGER NOT NULL,
      media_url TEXT DEFAULT '',
      answer_text TEXT DEFAULT '',
      feedback_text TEXT DEFAULT '',
      grade INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (homework_task_id) REFERENCES homework_tasks(id),
      FOREIGN KEY (student_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      student_id INTEGER NOT NULL,
      rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
      comment TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(course_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS purchases (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      student_id INTEGER NOT NULL,
      amount_cents INTEGER NOT NULL,
      platform_fee_cents INTEGER NOT NULL,
      instructor_earnings_cents INTEGER NOT NULL,
      payment_id TEXT DEFAULT '',
      payment_status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (course_id) REFERENCES courses(id),
      FOREIGN KEY (student_id) REFERENCES users(id),
      UNIQUE(course_id, student_id)
    );

    CREATE TABLE IF NOT EXISTS purchase_devices (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      purchase_id INTEGER NOT NULL,
      device_hash TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(purchase_id, device_hash)
    );


    CREATE TABLE IF NOT EXISTS favorites (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id INTEGER NOT NULL,
      course_id INTEGER NOT NULL,
      UNIQUE(student_id, course_id)
    );

    CREATE TABLE IF NOT EXISTS certificates_issued (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id INTEGER NOT NULL,
      course_id INTEGER NOT NULL,
      cert_code TEXT NOT NULL UNIQUE,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS before_after_results (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id INTEGER NOT NULL,
      course_id INTEGER NOT NULL,
      before_url TEXT DEFAULT '',
      after_url TEXT DEFAULT '',
      caption TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
  `);

  const adminEmail = process.env.ADMIN_EMAIL || 'admin@beauty.local';
  const admin = db.prepare('SELECT id FROM users WHERE email = ?').get(adminEmail);
  if (!admin) {
    db.prepare('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)').run(
      'Platform Admin',
      adminEmail,
      bcrypt.hashSync(process.env.ADMIN_PASSWORD || 'admin123', 10),
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
    saveUninitialized: false
  })
);

app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  res.locals.formatMoney = (cents) => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }).format((cents || 0) / 100);
  res.locals.commissionPercent = Math.round(PLATFORM_COMMISSION_RATE * 100);
  next();
});

const requireAuth = (req, res, next) => (req.session.user ? next() : res.redirect('/login'));
const requireRole = (...roles) => (req, res, next) => (req.session.user && roles.includes(req.session.user.role) ? next() : res.status(403).send('Доступ запрещён'));

function base64Auth(shopId, secret) {
  return Buffer.from(`${shopId}:${secret}`).toString('base64');
}

async function createYooKassaPayment({ amountRub, description, returnUrl, idempotenceKey }) {
  const body = {
    amount: { value: amountRub.toFixed(2), currency: 'RUB' },
    capture: true,
    confirmation: { type: 'redirect', return_url: returnUrl },
    description
  };
  const response = await fetch('https://api.yookassa.ru/v3/payments', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Basic ${base64Auth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)}`,
      'Idempotence-Key': idempotenceKey
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`YooKassa error: ${response.status} ${text}`);
  }
  return response.json();
}

function refreshInstructorRating(instructorId) {
  const row = db.prepare(`
    SELECT COALESCE(AVG(r.rating),0) AS avg_rating
    FROM reviews r
    JOIN courses c ON c.id = r.course_id
    WHERE c.instructor_id = ?
  `).get(instructorId);
  db.prepare('UPDATE users SET rating = ? WHERE id = ?').run(Number(row.avg_rating || 0).toFixed(2), instructorId);
}

app.get('/', (req, res) => {
  const { q = '', category = '', level = '', language = '', maxPrice = '', minRating = '' } = req.query;
  const filters = ['c.published = 1'];
  const params = [];
  if (q) { filters.push('(c.title LIKE ? OR c.description LIKE ?)'); params.push(`%${q}%`, `%${q}%`); }
  if (category) { filters.push('c.category = ?'); params.push(category); }
  if (level) { filters.push('c.level = ?'); params.push(level); }
  if (language) { filters.push('c.language = ?'); params.push(language); }
  if (maxPrice) { filters.push('c.price_cents <= ?'); params.push(Math.round(Number(maxPrice) * 100)); }
  if (minRating) { filters.push('COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.course_id = c.id), 0) >= ?'); params.push(Number(minRating)); }

  const courses = db.prepare(`
    SELECT c.*, u.name AS instructor_name, u.id instructor_id, u.rating,
      (SELECT COUNT(*) FROM purchases p WHERE p.course_id = c.id AND p.payment_status='paid') sales_count,
      (SELECT AVG(r.rating) FROM reviews r WHERE r.course_id = c.id) AS avg_rating
    FROM courses c
    JOIN users u ON u.id = c.instructor_id
    WHERE ${filters.join(' AND ')}
    ORDER BY c.created_at DESC
  `).all(...params);

  const popularCourses = db.prepare(`
    SELECT c.id, c.title, c.price_cents, c.thumbnail_url,
    COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.course_id = c.id), 0) as rating
    FROM courses c
    WHERE c.published = 1
    ORDER BY rating DESC, c.created_at DESC
    LIMIT 6
  `).all();

  const topMasters = db.prepare("SELECT id,name,rating,specialization FROM users WHERE role='instructor' ORDER BY rating DESC, created_at DESC LIMIT 8").all();
  const beforeAfter = db.prepare("SELECT * FROM before_after_results ORDER BY created_at DESC LIMIT 6").all();
  const testimonials = db.prepare("SELECT r.rating, r.comment, u.name as student_name FROM reviews r JOIN users u ON u.id = r.student_id ORDER BY r.created_at DESC LIMIT 6").all();

  res.render('home', { courses, popularCourses, topMasters, beforeAfter, testimonials, categoryOptions, levelOptions, languageOptions, q: req.query });
});

app.get('/register', (req, res) => res.render('register', { error: null }));
app.post('/register', (req, res) => {
  const { name, email, password, role } = req.body;
  if (!name || !email || !password || !['student', 'instructor'].includes(role)) {
    return res.status(400).render('register', { error: 'Проверьте заполнение полей.' });
  }
  try {
    const r = db.prepare('INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)').run(name, email.toLowerCase(), bcrypt.hashSync(password, 10), role);
    req.session.user = { id: r.lastInsertRowid, name, email: email.toLowerCase(), role };
    res.redirect('/dashboard');
  } catch {
    res.status(400).render('register', { error: 'Email уже занят.' });
  }
});

app.get('/login', (req, res) => res.render('login', { error: null }));
app.post('/login', (req, res) => {
  const user = db.prepare('SELECT * FROM users WHERE email = ?').get((req.body.email || '').toLowerCase());
  if (!user || !bcrypt.compareSync(req.body.password || '', user.password_hash)) {
    return res.status(400).render('login', { error: 'Неверный логин или пароль.' });
  }
  req.session.user = { id: user.id, name: user.name, email: user.email, role: user.role };
  res.redirect('/dashboard');
});

app.post('/logout', (req, res) => req.session.destroy(() => res.redirect('/')));

app.get('/dashboard', requireAuth, (req, res) => {
  if (req.session.user.role === 'instructor') {
    const profile = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.user.id);
    const courses = db.prepare('SELECT * FROM courses WHERE instructor_id = ? ORDER BY created_at DESC').all(req.session.user.id);
    const stats = db.prepare(`
      SELECT COALESCE(SUM(amount_cents),0) gross, COALESCE(SUM(platform_fee_cents),0) platform, COALESCE(SUM(instructor_earnings_cents),0) payout
      FROM purchases p JOIN courses c ON c.id = p.course_id
      WHERE c.instructor_id = ? AND p.payment_status='paid'
    `).get(req.session.user.id);
    return res.render('dashboard_instructor', { profile, courses, stats });
  }

  if (req.session.user.role === 'admin') {
    const stats = db.prepare(`SELECT COALESCE(SUM(amount_cents),0) gross, COALESCE(SUM(platform_fee_cents),0) commission, COUNT(*) sales FROM purchases WHERE payment_status='paid'`).get();
    return res.render('dashboard_admin', { stats, topCourses: db.prepare('SELECT title FROM courses ORDER BY created_at DESC LIMIT 10').all() });
  }

  const myCourses = db.prepare(`
    SELECT c.*, p.created_at purchase_date, u.name instructor_name
    FROM purchases p JOIN courses c ON c.id = p.course_id JOIN users u ON u.id = c.instructor_id
    WHERE p.student_id = ? AND p.payment_status='paid'
    ORDER BY p.created_at DESC
  `).all(req.session.user.id);

  const submissions = db.prepare(`
    SELECT hs.*, ht.title task_title
    FROM homework_submissions hs
    JOIN homework_tasks ht ON ht.id = hs.homework_task_id
    WHERE hs.student_id = ?
    ORDER BY hs.created_at DESC
  `).all(req.session.user.id);

  res.render('dashboard_student', { myCourses, submissions });
});

app.get('/instructor/profile', requireAuth, requireRole('instructor'), (req, res) => {
  const profile = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.user.id);
  res.render('instructor_profile', { profile, saved: req.query.saved });
});
app.post('/instructor/profile', requireAuth, requireRole('instructor'), (req, res) => {
  const { specialization = '', experience_years = 0, certificates = '', portfolio_text = '', social_instagram = '', social_telegram = '' } = req.body;
  db.prepare(`UPDATE users SET specialization=?, experience_years=?, certificates=?, portfolio_text=?, social_instagram=?, social_telegram=? WHERE id=?`)
    .run(specialization, Number(experience_years) || 0, certificates, portfolio_text, social_instagram, social_telegram, req.session.user.id);
  res.redirect('/instructor/profile?saved=1');
});

app.get('/instructors/:id', (req, res) => {
  const instructor = db.prepare('SELECT * FROM users WHERE id = ? AND role = ?').get(req.params.id, 'instructor');
  if (!instructor) return res.status(404).send('Мастер не найден');
  const reviews = db.prepare(`
    SELECT r.*, u.name student_name, c.title course_title
    FROM reviews r JOIN users u ON u.id = r.student_id JOIN courses c ON c.id = r.course_id
    WHERE c.instructor_id = ?
    ORDER BY r.created_at DESC
  `).all(instructor.id);
  const courses = db.prepare('SELECT * FROM courses WHERE instructor_id = ? AND published = 1').all(instructor.id);
  res.render('instructor_show', { instructor, reviews, courses });
});

app.get('/courses/new', requireAuth, requireRole('instructor'), (req, res) => {
  res.render('course_new', { error: null, categoryOptions, levelOptions, languageOptions });
});

app.post('/courses', requireAuth, requireRole('instructor'), (req, res) => {
  const { title, category, description, level, language, duration_hours, price, thumbnail_url } = req.body;
  if (!title || !description) return res.status(400).render('course_new', { error: 'Заполните обязательные поля.', categoryOptions, levelOptions, languageOptions });
  const r = db.prepare(`
    INSERT INTO courses (instructor_id, title, category, description, level, language, duration_hours, price_cents, thumbnail_url, published)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
  `).run(req.session.user.id, title, category, description, level, language, Number(duration_hours) || 1, Math.max(100, Math.round(Number(price || 1) * 100)), thumbnail_url || '');

  const module = db.prepare('INSERT INTO modules (course_id, title, position) VALUES (?, ?, 1)').run(r.lastInsertRowid, 'Модуль 1');
  db.prepare('INSERT INTO lessons (module_id, title, text_content, position, duration_min) VALUES (?, ?, ?, 1, 10)').run(module.lastInsertRowid, 'Урок 1', 'Вступление к курсу');
  res.redirect(`/courses/${r.lastInsertRowid}/builder`);
});

app.get('/courses/:id/builder', requireAuth, requireRole('instructor'), (req, res) => {
  const course = db.prepare('SELECT * FROM courses WHERE id = ? AND instructor_id = ?').get(req.params.id, req.session.user.id);
  if (!course) return res.status(404).send('Курс не найден');
  const modules = db.prepare('SELECT * FROM modules WHERE course_id = ? ORDER BY position').all(course.id);
  const moduleWithLessons = modules.map((m) => ({
    ...m,
    lessons: db.prepare('SELECT * FROM lessons WHERE module_id = ? ORDER BY position').all(m.id)
  }));
  const materials = db.prepare('SELECT * FROM materials WHERE course_id = ? ORDER BY id DESC').all(course.id);
  const homeworkTasks = db.prepare(`SELECT ht.*, l.title lesson_title FROM homework_tasks ht JOIN lessons l ON l.id = ht.lesson_id JOIN modules m ON m.id = l.module_id WHERE m.course_id = ?`).all(course.id);
  res.render('course_builder', { course, modules: moduleWithLessons, materials, homeworkTasks });
});

app.post('/courses/:id/modules', requireAuth, requireRole('instructor'), (req, res) => {
  const course = db.prepare('SELECT * FROM courses WHERE id = ? AND instructor_id = ?').get(req.params.id, req.session.user.id);
  if (!course) return res.status(404).send('Курс не найден');
  const maxPos = db.prepare('SELECT COALESCE(MAX(position), 0) max_pos FROM modules WHERE course_id = ?').get(course.id).max_pos;
  db.prepare('INSERT INTO modules (course_id, title, position) VALUES (?, ?, ?)').run(course.id, req.body.title || 'Новый модуль', maxPos + 1);
  res.redirect(`/courses/${course.id}/builder`);
});

app.post('/modules/:id/lessons', requireAuth, requireRole('instructor'), (req, res) => {
  const mod = db.prepare(`SELECT m.* FROM modules m JOIN courses c ON c.id = m.course_id WHERE m.id = ? AND c.instructor_id = ?`).get(req.params.id, req.session.user.id);
  if (!mod) return res.status(404).send('Модуль не найден');
  const maxPos = db.prepare('SELECT COALESCE(MAX(position),0) max_pos FROM lessons WHERE module_id = ?').get(mod.id).max_pos;
  db.prepare('INSERT INTO lessons (module_id,title,video_url,text_content,position,duration_min) VALUES (?,?,?,?,?,?)')
    .run(mod.id, req.body.title || 'Новый урок', req.body.video_url || '', req.body.text_content || '', maxPos + 1, Number(req.body.duration_min) || 10);
  res.redirect(`/courses/${mod.course_id}/builder`);
});

app.post('/courses/:id/materials', requireAuth, requireRole('instructor'), (req, res) => {
  const course = db.prepare('SELECT * FROM courses WHERE id = ? AND instructor_id = ?').get(req.params.id, req.session.user.id);
  if (!course) return res.status(404).send('Курс не найден');
  db.prepare('INSERT INTO materials (course_id,title,type,content_url,content_text) VALUES (?,?,?,?,?)')
    .run(course.id, req.body.title || 'Материал', req.body.type || 'text', req.body.content_url || '', req.body.content_text || '');
  res.redirect(`/courses/${course.id}/builder`);
});

app.post('/courses/:id/homework', requireAuth, requireRole('instructor'), (req, res) => {
  const lesson = db.prepare(`SELECT l.*, m.course_id FROM lessons l JOIN modules m ON m.id = l.module_id JOIN courses c ON c.id = m.course_id WHERE l.id = ? AND c.instructor_id = ?`).get(req.body.lesson_id, req.session.user.id);
  if (!lesson) return res.status(404).send('Урок не найден');
  db.prepare('INSERT INTO homework_tasks (lesson_id,title,instructions) VALUES (?,?,?)').run(lesson.id, req.body.title || 'Домашка', req.body.instructions || '');
  res.redirect(`/courses/${req.params.id}/builder`);
});

app.post('/lessons/reorder', requireAuth, requireRole('instructor'), (req, res) => {
  const ids = String(req.body.lesson_ids || '').split(',').map((n) => Number(n)).filter(Boolean);
  ids.forEach((id, i) => db.prepare('UPDATE lessons SET position = ? WHERE id = ?').run(i + 1, id));
  res.redirect(req.get('referer') || '/dashboard');
});

app.get('/courses/:id', (req, res) => {
  const course = db.prepare(`
    SELECT c.*, u.name instructor_name, u.id instructor_id, u.rating instructor_rating
    FROM courses c JOIN users u ON u.id = c.instructor_id
    WHERE c.id = ? AND c.published = 1
  `).get(req.params.id);
  if (!course) return res.status(404).send('Курс не найден');

  const modules = db.prepare('SELECT * FROM modules WHERE course_id = ? ORDER BY position').all(course.id)
    .map((m) => ({ ...m, lessons: db.prepare('SELECT * FROM lessons WHERE module_id = ? ORDER BY position').all(m.id) }));

  const materials = db.prepare('SELECT * FROM materials WHERE course_id = ?').all(course.id);
  const reviews = db.prepare('SELECT r.*, u.name student_name FROM reviews r JOIN users u ON u.id = r.student_id WHERE r.course_id = ? ORDER BY r.created_at DESC').all(course.id);
  const similarCourses = db.prepare('SELECT id,title,price_cents FROM courses WHERE category = ? AND id != ? AND published = 1 LIMIT 4').all(course.category, course.id);

  let purchase = null;
  if (req.session.user && req.session.user.role === 'student') {
    purchase = db.prepare('SELECT * FROM purchases WHERE course_id = ? AND student_id = ?').get(course.id, req.session.user.id);
  }

  res.render('course_show', {
    course,
    modules,
    materials,
    reviews,
    similarCourses,
    purchase,
    platformFeeCents: Math.round(course.price_cents * PLATFORM_COMMISSION_RATE),
    instructorEarningsCents: course.price_cents - Math.round(course.price_cents * PLATFORM_COMMISSION_RATE)
  });
});

app.post('/courses/:id/purchase', requireAuth, requireRole('student'), async (req, res) => {
  const course = db.prepare('SELECT * FROM courses WHERE id = ? AND published = 1').get(req.params.id);
  if (!course) return res.status(404).send('Курс не найден');

  const existing = db.prepare('SELECT * FROM purchases WHERE course_id = ? AND student_id = ?').get(course.id, req.session.user.id);
  if (existing && existing.payment_status === 'paid') return res.redirect(`/courses/${course.id}`);

  const platformFeeCents = Math.round(course.price_cents * PLATFORM_COMMISSION_RATE);
  const instructorEarningsCents = course.price_cents - platformFeeCents;
  let purchaseId = existing ? existing.id : null;

  if (!purchaseId) {
    purchaseId = db.prepare(`INSERT INTO purchases (course_id, student_id, amount_cents, platform_fee_cents, instructor_earnings_cents, payment_status) VALUES (?, ?, ?, ?, ?, 'pending')`)
      .run(course.id, req.session.user.id, course.price_cents, platformFeeCents, instructorEarningsCents).lastInsertRowid;
  }

  if (YOOKASSA_SHOP_ID && YOOKASSA_SECRET_KEY) {
    try {
      const yk = await createYooKassaPayment({
        amountRub: course.price_cents / 100,
        description: `Оплата курса: ${course.title}`,
        returnUrl: `${req.protocol}://${req.get('host')}/payments/success?purchase=${purchaseId}`,
        idempotenceKey: crypto.randomUUID()
      });
      db.prepare('UPDATE purchases SET payment_id = ? WHERE id = ?').run(yk.id, purchaseId);
      return res.redirect(yk.confirmation.confirmation_url);
    } catch {
      db.prepare('UPDATE purchases SET payment_status = ? WHERE id = ?').run('failed', purchaseId);
      return res.status(502).send('Ошибка оплаты YooKassa. Проверьте ключи и повторите.');
    }
  }

  db.prepare('UPDATE purchases SET payment_status = ? WHERE id = ?').run('paid', purchaseId);
  res.redirect('/dashboard');
});

app.get('/payments/success', requireAuth, requireRole('student'), (req, res) => {
  const purchase = db.prepare('SELECT * FROM purchases WHERE id = ? AND student_id = ?').get(req.query.purchase, req.session.user.id);
  if (!purchase) return res.redirect('/dashboard');
  db.prepare('UPDATE purchases SET payment_status = ? WHERE id = ?').run('paid', purchase.id);
  res.redirect('/dashboard');
});

app.post('/purchases/:id/refund', requireAuth, requireRole('student'), (req, res) => {
  const purchase = db.prepare('SELECT * FROM purchases WHERE id = ? AND student_id = ? AND payment_status = ?').get(req.params.id, req.session.user.id, 'paid');
  if (!purchase) return res.redirect('/dashboard');
  const withinWindow = (Date.now() - new Date(purchase.created_at).getTime()) < (14 * 24 * 60 * 60 * 1000);
  if (!withinWindow) return res.status(400).send('Срок гарантированного возврата 14 дней истек.');
  db.prepare('UPDATE purchases SET payment_status = ? WHERE id = ?').run('refunded', purchase.id);
  res.redirect('/dashboard');
});

app.get('/lessons/:id/watch', requireAuth, requireRole('student'), (req, res) => {
  const lesson = db.prepare(`
    SELECT l.*, c.id course_id, c.title course_title, p.id purchase_id
    FROM lessons l
    JOIN modules m ON m.id = l.module_id
    JOIN courses c ON c.id = m.course_id
    JOIN purchases p ON p.course_id = c.id
    WHERE l.id = ? AND p.student_id = ? AND p.payment_status='paid'
  `).get(req.params.id, req.session.user.id);
  if (!lesson) return res.status(403).send('У вас нет доступа к уроку');

  const deviceHash = crypto.createHash('sha256').update((req.headers['user-agent'] || 'ua') + req.ip).digest('hex');
  db.prepare('INSERT OR IGNORE INTO purchase_devices (purchase_id, device_hash) VALUES (?, ?)').run(lesson.purchase_id, deviceHash);
  const count = db.prepare('SELECT COUNT(*) cnt FROM purchase_devices WHERE purchase_id = ?').get(lesson.purchase_id).cnt;
  if (count > 2) return res.status(403).send('Превышен лимит устройств (2).');

  const homework = db.prepare('SELECT * FROM homework_tasks WHERE lesson_id = ?').all(lesson.id);
  res.render('lesson_watch', { lesson, homework, watermark: req.session.user.name });
});

app.post('/homework/:id/submit', requireAuth, requireRole('student'), (req, res) => {
  db.prepare('INSERT INTO homework_submissions (homework_task_id, student_id, media_url, answer_text) VALUES (?, ?, ?, ?)')
    .run(req.params.id, req.session.user.id, req.body.media_url || '', req.body.answer_text || '');
  res.redirect('/dashboard');
});

app.post('/submissions/:id/feedback', requireAuth, requireRole('instructor'), (req, res) => {
  const sub = db.prepare(`
    SELECT hs.id FROM homework_submissions hs
    JOIN homework_tasks ht ON ht.id = hs.homework_task_id
    JOIN lessons l ON l.id = ht.lesson_id
    JOIN modules m ON m.id = l.module_id
    JOIN courses c ON c.id = m.course_id
    WHERE hs.id = ? AND c.instructor_id = ?
  `).get(req.params.id, req.session.user.id);
  if (!sub) return res.status(404).send('Работа не найдена');
  db.prepare('UPDATE homework_submissions SET feedback_text = ?, grade = ? WHERE id = ?').run(req.body.feedback_text || '', Number(req.body.grade) || 0, req.params.id);
  res.redirect(req.get('referer') || '/dashboard');
});

app.post('/courses/:id/review', requireAuth, requireRole('student'), (req, res) => {
  const purchase = db.prepare('SELECT * FROM purchases WHERE course_id = ? AND student_id = ? AND payment_status = ?').get(req.params.id, req.session.user.id, 'paid');
  if (!purchase) return res.status(403).send('Оценку можно оставить только после покупки.');
  db.prepare('INSERT OR REPLACE INTO reviews (course_id, student_id, rating, comment) VALUES (?, ?, ?, ?)')
    .run(req.params.id, req.session.user.id, Number(req.body.rating) || 5, req.body.comment || '');
  const instructorId = db.prepare('SELECT instructor_id FROM courses WHERE id = ?').get(req.params.id).instructor_id;
  refreshInstructorRating(instructorId);
  res.redirect(`/courses/${req.params.id}`);
});



app.get('/masters', (req, res) => {
  const masters = db.prepare("SELECT id,name,specialization,experience_years,rating,portfolio_text FROM users WHERE role='instructor' ORDER BY rating DESC, created_at DESC").all();
  res.render('masters', { masters });
});

app.get('/forgot-password', (req, res) => res.render('forgot_password', { sent: req.query.sent }));
app.post('/forgot-password', (req, res) => res.redirect('/forgot-password?sent=1'));

app.post('/favorites/:courseId', requireAuth, requireRole('student'), (req, res) => {
  db.prepare('INSERT OR IGNORE INTO favorites (student_id, course_id) VALUES (?, ?)').run(req.session.user.id, req.params.courseId);
  res.redirect(req.get('referer') || '/dashboard');
});

app.post('/courses/:id/certify', requireAuth, requireRole('student'), (req, res) => {
  const purchase = db.prepare("SELECT id FROM purchases WHERE student_id=? AND course_id=? AND payment_status='paid'").get(req.session.user.id, req.params.id);
  if (!purchase) return res.status(403).send('Сначала купите курс');
  const code = `BS-${req.params.id}-${req.session.user.id}-${Date.now()}`;
  db.prepare('INSERT INTO certificates_issued (student_id, course_id, cert_code) VALUES (?,?,?)').run(req.session.user.id, req.params.id, code);
  res.redirect('/dashboard/student/certificates');
});

app.post('/courses/:id/results', requireAuth, requireRole('student'), (req, res) => {
  db.prepare('INSERT INTO before_after_results (student_id, course_id, before_url, after_url, caption) VALUES (?, ?, ?, ?, ?)')
    .run(req.session.user.id, req.params.id, req.body.before_url || '', req.body.after_url || '', req.body.caption || '');
  res.redirect(`/courses/${req.params.id}`);
});

app.get('/dashboard/student/progress', requireAuth, requireRole('student'), (req, res) => {
  const progress = db.prepare(`
    SELECT c.title, COUNT(l.id) total_lessons,
      SUM(CASE WHEN l.id IN (SELECT lesson_id FROM homework_tasks ht JOIN homework_submissions hs ON hs.homework_task_id = ht.id WHERE hs.student_id = ?) THEN 1 ELSE 0 END) completed_items
    FROM purchases p
    JOIN courses c ON c.id = p.course_id
    JOIN modules m ON m.course_id = c.id
    JOIN lessons l ON l.module_id = m.id
    WHERE p.student_id = ? AND p.payment_status='paid'
    GROUP BY c.id
  `).all(req.session.user.id, req.session.user.id);
  res.render('student_progress', { progress });
});

app.get('/dashboard/student/certificates', requireAuth, requireRole('student'), (req, res) => {
  const certs = db.prepare(`SELECT ci.*, c.title FROM certificates_issued ci JOIN courses c ON c.id = ci.course_id WHERE ci.student_id = ? ORDER BY ci.created_at DESC`).all(req.session.user.id);
  res.render('student_certificates', { certs });
});

app.get('/dashboard/student/favorites', requireAuth, requireRole('student'), (req, res) => {
  const favorites = db.prepare(`SELECT c.* FROM favorites f JOIN courses c ON c.id = f.course_id WHERE f.student_id = ?`).all(req.session.user.id);
  res.render('student_favorites', { favorites });
});

app.get('/dashboard/student/purchases', requireAuth, requireRole('student'), (req, res) => {
  const purchases = db.prepare(`SELECT p.*, c.title FROM purchases p JOIN courses c ON c.id = p.course_id WHERE p.student_id = ? ORDER BY p.created_at DESC`).all(req.session.user.id);
  res.render('student_purchases', { purchases });
});

app.get('/dashboard/student/settings', requireAuth, requireRole('student'), (req, res) => {
  const profile = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.user.id);
  res.render('student_settings', { profile, saved: req.query.saved });
});
app.post('/dashboard/student/settings', requireAuth, requireRole('student'), (req, res) => {
  db.prepare('UPDATE users SET name=? WHERE id=?').run(req.body.name || 'Ученик', req.session.user.id);
  req.session.user.name = req.body.name || req.session.user.name;
  res.redirect('/dashboard/student/settings?saved=1');
});

app.get('/dashboard/instructor/students', requireAuth, requireRole('instructor'), (req, res) => {
  const students = db.prepare(`
    SELECT u.name, u.email, c.title, p.created_at
    FROM purchases p JOIN users u ON u.id=p.student_id JOIN courses c ON c.id=p.course_id
    WHERE c.instructor_id=? AND p.payment_status='paid'
    ORDER BY p.created_at DESC
  `).all(req.session.user.id);
  res.render('instructor_students', { students });
});

app.get('/dashboard/instructor/homework', requireAuth, requireRole('instructor'), (req, res) => {
  const submissions = db.prepare(`
    SELECT hs.*, u.name student_name, ht.title task_title
    FROM homework_submissions hs
    JOIN users u ON u.id = hs.student_id
    JOIN homework_tasks ht ON ht.id = hs.homework_task_id
    JOIN lessons l ON l.id = ht.lesson_id
    JOIN modules m ON m.id = l.module_id
    JOIN courses c ON c.id = m.course_id
    WHERE c.instructor_id = ?
    ORDER BY hs.created_at DESC
  `).all(req.session.user.id);
  res.render('instructor_homework', { submissions });
});

app.get('/dashboard/instructor/analytics', requireAuth, requireRole('instructor'), (req, res) => {
  const analytics = db.prepare(`
    SELECT c.title,
      COUNT(p.id) sales,
      COALESCE(SUM(p.amount_cents),0) revenue
    FROM courses c
    LEFT JOIN purchases p ON p.course_id = c.id AND p.payment_status='paid'
    WHERE c.instructor_id = ?
    GROUP BY c.id
    ORDER BY revenue DESC
  `).all(req.session.user.id);
  res.render('instructor_analytics', { analytics });
});

app.get('/dashboard/instructor/finances', requireAuth, requireRole('instructor'), (req, res) => {
  const payouts = db.prepare(`SELECT p.*, c.title FROM purchases p JOIN courses c ON c.id = p.course_id WHERE c.instructor_id = ? AND p.payment_status='paid' ORDER BY p.created_at DESC`).all(req.session.user.id);
  res.render('instructor_finances', { payouts });
});

app.get('/dashboard/instructor/webinars', requireAuth, requireRole('instructor'), (req, res) => res.render('instructor_webinars'));

app.get('/messages', requireAuth, (req, res) => res.render('messages'));
app.get('/notifications', requireAuth, (req, res) => res.render('notifications'));

app.get('/about', (req, res) => res.render('static_page', { title: 'О платформе', content: 'BeautyScale — платформа обучения бьюти-мастеров.' }));
app.get('/faq', (req, res) => res.render('static_page', { title: 'FAQ', content: 'Частые вопросы по оплате, доступу и возвратам.' }));
app.get('/blog', (req, res) => res.render('blog'));
app.get('/privacy', (req, res) => res.render('static_page', { title: 'Политика конфиденциальности', content: 'Мы защищаем ваши персональные данные.' }));
app.get('/terms', (req, res) => res.render('static_page', { title: 'Пользовательское соглашение', content: 'Условия использования платформы.' }));

app.get('/admin/moderation', requireAuth, requireRole('admin'), (req, res) => res.render('admin_moderation'));
app.get('/admin/users', requireAuth, requireRole('admin'), (req, res) => res.render('admin_users', { users: db.prepare('SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC').all() }));
app.get('/admin/finances', requireAuth, requireRole('admin'), (req, res) => res.render('admin_finances', { rows: db.prepare('SELECT * FROM purchases ORDER BY created_at DESC').all() }));
app.get('/admin/complaints', requireAuth, requireRole('admin'), (req, res) => res.render('admin_complaints'));
app.get('/admin/analytics', requireAuth, requireRole('admin'), (req, res) => res.render('admin_analytics'));

app.listen(PORT, () => console.log(`BeautyScale running on http://localhost:${PORT}`));
