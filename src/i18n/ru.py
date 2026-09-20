"""Russian catalogue. The key is the English source string."""

RU = {
    # --- app bar ---------------------------------------------------------
    "Not logged in": "Вход не выполнен",
    "Logged in": "Вход выполнен",
    "To download private content available to you, log in the app": (
        "Чтобы скачивать платный контент, доступный вам, войдите в приложение"
    ),
    # --- welcome page ----------------------------------------------------
    "One post": "Один пост",
    "download a specific author's post via a direct link": (
        "скачать конкретный пост автора по прямой ссылке"
    ),
    "Several posts": "Несколько постов",
    "download an author's posts over a given time period": (
        "скачать посты автора за выбранный период"
    ),
    "More": "Ещё",
    "Give feedback or report a bug": "Оставить отзыв или сообщить об ошибке",
    "Merge author's content": "Собрать контент автора",
    "Download image by link": "Скачать изображение по ссылке",
    # --- settings --------------------------------------------------------
    "Settings": "Настройки",
    "A modified fork of Boosty downloader by {author}": (
        "Изменённый форк Boosty downloader, автор оригинала — {author}:"
    ),
    "Fetching...": "Загрузка...",
    "Download folder": "Папка загрузки",
    "App theme": "Тема оформления",
    "App language": "Язык приложения",
    "Content settings": "Что скачивать",
    "Download settings": "Настройки загрузки",
    "Download photos": "Скачивать фотографии",
    "Download videos": "Скачивать видео",
    "Download audios": "Скачивать аудио",
    "Download attached files": "Скачивать вложенные файлы",
    "Restrict video size": "Ограничение качества видео",
    "Low": "Низкое",
    "Medium": "Среднее",
    "High": "Высокое",
    "Full HD": "Full HD",
    "Ultra HD (no restrict)": "Ultra HD (без ограничения)",
    "Post text format": "Формат текста поста",
    "Markdown file (.md)": "Файл Markdown (.md)",
    "Text file (.txt)": "Текстовый файл (.txt)",
    "Folder and file names": "Имена папок и файлов",
    "Archive: date in folder, numbered files": (
        "Архивная: дата в папке, файлы с номерами"
    ),
    "Original: post id in names": "Как у автора: id поста в именах",
    "Chunk size": "Размер блока загрузки",
    "Download timeout (sec.)": "Тайм-аут загрузки (сек.)",
    "Maximum download parallelism": "Максимум параллельных загрузок",
    "Save": "Сохранить",
    "Saved": "Сохранено",
    "Please enter value between 10000 and 500000.": (
        "Введите значение от 10000 до 500000."
    ),
    "Not recommended to set timeout less, than 10 seconds.": (
        "Не рекомендуется ставить тайм-аут меньше 10 секунд."
    ),
    "Please enter value between 1 and 10.": "Введите значение от 1 до 10.",
    "Understand": "Понятно",
    # --- theme picker ----------------------------------------------------
    "Light": "Светлая",
    "Dark": "Тёмная",
    "System": "Как в системе",
    # --- authorization ---------------------------------------------------
    "Authorization management": "Управление входом",
    "Copy login script": "Скопировать скрипт входа",
    "1. Copy script": "1. Скопируйте скрипт",
    "Click the button to copy script:": "Нажмите кнопку, чтобы скопировать скрипт:",
    "2. Paste script into the browser console on boosty": (
        "2. Вставьте скрипт в консоль браузера на Boosty"
    ),
    "Make sure that you are logged in to your account on the website.": (
        "Убедитесь, что вы вошли в свой аккаунт на сайте."
    ),
    "Press the F12 key when you are on the boosty page, and then paste the text into the console.": (
        "Нажмите F12 на странице Boosty и вставьте текст в консоль."
    ),
    "If the browser shows a warning about code insertion, follow its instructions. Usually you just need to enter 'allow pasting' and press enter.": (
        "Если браузер предупреждает о вставке кода, следуйте его указаниям. "
        "Обычно достаточно ввести «allow pasting» и нажать Enter."
    ),
    "3. Authorize app": "3. Авторизуйте приложение",
    "Copy the token that appeared in the browser console and paste it here:": (
        "Скопируйте токен, появившийся в консоли браузера, и вставьте его сюда:"
    ),
    "Save token": "Сохранить токен",
    "Logout": "Выйти",
    "Empty token": "Пустой токен",
    "Type token from console into the text field": (
        "Вставьте токен из консоли в поле ввода"
    ),
    "Token is incorrect": "Токен неверный",
    "Are you sure you copied it completely?": "Вы точно скопировали его целиком?",
    "Ops, ok": "Понятно",
    "I'll check": "Проверю",
    "Token will valid for {days} days, {tail}": (
        "Вход действителен ещё {days} дн., {tail}"
    ),
    "Token will valid for {tail}": "Вход действителен ещё {tail}",
    "{minutes} minutes.": "{minutes} мин.",
    "{hours} hours.": "{hours} ч.",
    # --- download post ---------------------------------------------------
    "Download post": "Скачать пост",
    "Download": "Скачать",
    "Queued": "Добавлено в очередь",
    "Already in queue": "Уже в очереди",
    "Empty address": "Пустой адрес",
    "Type link to post into the text field": "Вставьте ссылку на пост в поле ввода",
    "Link to post seems invalid": "Ссылка на пост выглядит неверной",
    "It looks like you entered an incorrect link": (
        "Похоже, вы ввели некорректную ссылку"
    ),
    # --- download several posts ------------------------------------------
    "Download several posts": "Скачать несколько постов",
    "Download posts published at:": "Скачать посты, опубликованные:",
    "Preparing...": "Подготовка...",
    "Searching posts by your criteria...": "Ищу посты по вашим условиям...",
    "Creating tasks in the manager": "Создаю задачи в менеджере",
    "{count} posts found": "Найдено постов: {count}",
    "{count} tasks created": "Создано задач: {count}",
    "Empty author": "Автор не указан",
    "Type link to author's page or author's nickname": (
        "Вставьте ссылку на страницу автора или его никнейм"
    ),
    "Wow, i'll": "Хорошо",
    "Empty page": "Пусто",
    "An error has occurred, or author have no posts. Please try again later.": (
        "Произошла ошибка, или у автора нет постов. Попробуйте позже."
    ),
    "Unexpected error on checking posts": "Непредвиденная ошибка при поиске постов",
    "An error has occurred when searching posts. Please, check url correctness or try again later.": (
        "Произошла ошибка при поиске постов. Проверьте ссылку или попробуйте позже."
    ),
    "Ok": "Хорошо",
    # --- what is new -----------------------------------------------------
    "What is new": "Что нового",
    "Paste a link to the author's page or the nickname, and the app will compare Boosty with what you already have": (
        "Вставьте ссылку на страницу автора или его никнейм — приложение "
        "сравнит Boosty с тем, что уже скачано"
    ),
    "Check": "Сверить",
    "Asking Boosty for the list of posts...": "Спрашиваю у Boosty список постов...",
    "{count} posts on Boosty": "Постов на Boosty: {count}",
    "{total} posts on Boosty, {have} already downloaded, {missing} missing": (
        "На Boosty {total}, уже скачано {have}, не хватает {missing}"
    ),
    "({locked} without access)": "(из них без доступа: {locked})",
    "Download what is missing": "Скачать недостающее",
    # --- download image by link ------------------------------------------
    "Choose download folder": "Выберите папку для загрузки",
    "Paste here link to the image (from feed or direct messages)": (
        "Вставьте сюда ссылку на изображение (из ленты или личных сообщений)"
    ),
    "Not this link": "Не та ссылка",
    "This utility is for download a PICTURE using a direct link (to picture) from the posts list or private messages (you can get this link in the browser address bar).": (
        "Этот инструмент скачивает ИЗОБРАЖЕНИЕ по прямой ссылке на картинку "
        "из ленты постов или личных сообщений. Такую ссылку видно в адресной "
        "строке браузера."
    ),
    "I get it": "Понятно",
    "Folder does not exist": "Папка не существует",
    "Download folder does not exist": "Папка загрузки не существует",
    "Ok, i'll create": "Хорошо, создам",
    "Already exists": "Уже есть",
    "File with this name already exists": "Файл с таким именем уже существует",
    "Understood": "Понятно",
    # --- downloads center ------------------------------------------------
    "Downloads center": "Центр загрузок",
    "Cancel all": "Отменить все",
    "In progress: {pending} / {total}": "В работе: {pending} / {total}",
    "Complete": "Готово",
    "{count} files, {weight}": "Файлов: {count}, {weight}",
    "{size} MB": "{size} МБ",
    "{size} GB": "{size} ГБ",
    # --- task errors -----------------------------------------------------
    "Cancelled": "Отменено",
    "An error has occurred": "Произошла ошибка",
    "Don't have access to post": "Нет доступа к посту",
    "Download directory unavailable": "Папка загрузки недоступна",
    # --- content merger --------------------------------------------------
    "Content merger": "Сборка контента",
    "Transfer content from the author's post folders to one folder": (
        "Перенести контент из папок постов автора в одну папку"
    ),
    "Action": "Действие",
    "Copy": "Копировать",
    "Move": "Переместить",
    "Copied": "Скопировано.",
    "Moved": "Перемещено.",
    "Choose author's folder": "Выберите папку автора",
    "Choose destination folder": "Выберите папку назначения",
    "Photos": "Фотографии",
    "Videos": "Видео",
    "Audios": "Аудио",
    "Add post title to filename": "Добавлять название поста в имя файла",
    "Proceed": "Выполнить",
    "Working...": "Работаю...",
    "Done": "Готово",
    " {photos} photos, {videos} videos, {audios} audios from {posts} posts.": (
        " Фотографий: {photos}, видео: {videos}, аудио: {audios} " "из {posts} постов."
    ),
    # --- feedback --------------------------------------------------------
    "Feedback and bugs": "Отзывы и ошибки",
    "Copy diagnostic": "Скопировать диагностику",
    "New project discussion": "Создать обсуждение",
    "New project issue": "Создать issue",
    "If you'd like to leave feedback about the app or suggest a new feature, please create a discussion thread in the project repository:": (
        "Если хотите оставить отзыв о приложении или предложить новую "
        "возможность, создайте обсуждение в репозитории проекта:"
    ),
    "If you encounter a bug, please report it in the project issues section:": (
        "Если нашли ошибку, сообщите о ней в разделе issues проекта:"
    ),
    "To speed up the bug fix, please include diagnostic information with the issue:": (
        "Чтобы ошибку исправили быстрее, приложите к сообщению диагностику:"
    ),
    # --- saved post text -------------------------------------------------
    "Published {date}": "Опубликовано {date}",
    # --- exit dialog -----------------------------------------------------
    "Some downloads are incomplete": "Некоторые загрузки не завершены",
    "Are you sure you want to exit the app?": "Точно выйти из приложения?",
    "No": "Нет",
    "Yes": "Да",
}
