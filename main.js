const leftBoardContainer = document.querySelector(".left-board");
const rightBoardContainer = document.querySelector(".right-board");

const message = document.querySelector("#game-message");
const shotInput = document.querySelector("#shot-input");
const shootButton = document.querySelector("#shoot-button");


// ==========================================
// USTAWIENIA GRY
// ==========================================

const BOARD_SIZE = 10;

const letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];


// ==========================================
// PLANSZE
// ==========================================

// 0 = puste pole
// 1 = statek
// 2 = pudło
// 3 = trafienie

const playerBoard = createEmptyBoard();
const computerBoard = createEmptyBoard();


// ==========================================
// TWORZENIE PUSTEJ PLANSZY
// ==========================================

function createEmptyBoard() {

    const board = [];

    for (let row = 0; row < BOARD_SIZE; row++) {

        board[row] = [];

        for (let col = 0; col < BOARD_SIZE; col++) {
            board[row][col] = 0;
        }
    }

    return board;
}


// ==========================================
// TWORZENIE INTERFEJSU PLANSZY
// ==========================================

function createBoard(container, board, isPlayerBoard) {

    container.innerHTML = "";

    const boardElement = document.createElement("div");
    boardElement.classList.add("board");


    // Tworzymy 11 wierszy:
    // pierwszy = nagłówki
    // kolejne 10 = pola planszy

    for (let row = -1; row < BOARD_SIZE; row++) {

        const boardRow = document.createElement("div");
        boardRow.classList.add("board-row");


        // --------------------------------------
        // PIERWSZA KOLUMNA
        // --------------------------------------

        const rowHeader = document.createElement("span");

        rowHeader.classList.add(
            "board-tile",
            "header"
        );


        if (row === -1) {

            // Lewy górny róg
            rowHeader.classList.add("corner");

        } else {

            // Numery 1-10
            rowHeader.textContent = row + 1;
        }

        boardRow.appendChild(rowHeader);


        // --------------------------------------
        // POLA PLANSZY
        // --------------------------------------

        for (let col = 0; col < BOARD_SIZE; col++) {

            const tile = document.createElement("span");

            tile.classList.add("board-tile");


            // Pierwszy wiersz = litery A-J
            if (row === -1) {

                tile.classList.add("header");

                tile.textContent = letters[col];

            } else {

                // Normalne pole planszy

                if (board[row][col] === 1 && isPlayerBoard) {
                    tile.classList.add("ship");
                }


                // Strzał w pole

                if (board[row][col] === 2) {
                    tile.classList.add("miss");
                }


                // Trafienie

                if (board[row][col] === 3) {
                    tile.classList.add("hit");
                }


                // ----------------------------------
                // KLIKANIE PLANSZY PRZECIWNIKA
                // ----------------------------------

                if (!isPlayerBoard) {

                    tile.addEventListener("click", function () {

                        const coordinate =
                            letters[col] + (row + 1);

                        shoot(coordinate);
                    });
                }
            }

            boardRow.appendChild(tile);
        }

        boardElement.appendChild(boardRow);
    }

    container.appendChild(boardElement);
}


// ==========================================
// STATKI
// ==========================================

function placeShip(board, row, col, length, horizontal = true) {

    for (let i = 0; i < length; i++) {

        let currentRow = row;
        let currentCol = col;

        if (horizontal) {
            currentCol += i;
        } else {
            currentRow += i;
        }

        board[currentRow][currentCol] = 1;
    }
}


// ==========================================
// STATKI GRACZA
// ==========================================

// Na początek ustawiamy statki ręcznie.
// Później można tutaj zrobić rozmieszczanie statków
// przez gracza.

placeShip(playerBoard, 0, 0, 4, true);   // A1-D1
placeShip(playerBoard, 2, 2, 3, true);   // C3-E3
placeShip(playerBoard, 5, 5, 3, false);  // F6-F8
placeShip(playerBoard, 7, 1, 2, true);   // B8-C8


// ==========================================
// STATKI KOMPUTERA
// ==========================================

placeShip(computerBoard, 1, 1, 4, true);
placeShip(computerBoard, 3, 5, 3, false);
placeShip(computerBoard, 6, 2, 3, true);
placeShip(computerBoard, 8, 7, 2, false);


// ==========================================
// PIERWSZE WYŚWIETLENIE PLANSZ
// ==========================================

createBoard(
    leftBoardContainer,
    playerBoard,
    true
);

createBoard(
    rightBoardContainer,
    computerBoard,
    false
);


// ==========================================
// SPRAWDZANIE WSPÓŁRZĘDNYCH
// ==========================================

function parseCoordinate(coordinate) {

    coordinate = coordinate
        .trim()
        .toUpperCase();


    // Akceptujemy:
    // A1
    // B7
    // J10

    const match = coordinate.match(/^([A-J])(10|[1-9])$/);

    if (!match) {
        return null;
    }


    const letter = match[1];
    const number = Number(match[2]);


    const col = letters.indexOf(letter);
    const row = number - 1;


    return {
        row: row,
        col: col
    };
}


// ==========================================
// STRZAŁ GRACZA
// ==========================================

function shoot(coordinate) {

    const position = parseCoordinate(coordinate);


    // Nieprawidłowa współrzędna

    if (!position) {

        message.textContent =
            "Nieprawidłowe pole. Wpisz np. A1 albo J10.";

        return;
    }


    const row = position.row;
    const col = position.col;


    // Czy pole było już ostrzelane?

    if (
        computerBoard[row][col] === 2 ||
        computerBoard[row][col] === 3
    ) {

        message.textContent =
            "To pole było już ostrzelane.";

        return;
    }


    // --------------------------------------
    // TRAFIENIE
    // --------------------------------------

    if (computerBoard[row][col] === 1) {

        computerBoard[row][col] = 3;

        message.textContent =
            `Trafiony! ${letters[col]}${row + 1}`;

    }

    // --------------------------------------
    // PUDŁO
    // --------------------------------------

    else {

        computerBoard[row][col] = 2;

        message.textContent =
            `Pudło! ${letters[col]}${row + 1}`;
    }


    // Odświeżamy planszę przeciwnika

    createBoard(
        rightBoardContainer,
        computerBoard,
        false
    );


    // Komputer wykonuje swój strzał

    setTimeout(computerShoot, 700);
}


// ==========================================
// STRZAŁ KOMPUTERA
// ==========================================

function computerShoot() {

    let row;
    let col;


    // Szukamy losowego, nieostrzelanego pola

    do {

        row = Math.floor(Math.random() * BOARD_SIZE);
        col = Math.floor(Math.random() * BOARD_SIZE);

    } while (
        playerBoard[row][col] === 2 ||
        playerBoard[row][col] === 3
    );


    const coordinate =
        letters[col] + (row + 1);


    // --------------------------------------
    // TRAFIENIE
    // --------------------------------------

    if (playerBoard[row][col] === 1) {

        playerBoard[row][col] = 3;

        message.textContent =
            `Komputer trafił w ${coordinate}!`;

    }

    // --------------------------------------
    // PUDŁO
    // --------------------------------------

    else {

        playerBoard[row][col] = 2;

        message.textContent =
            `Komputer strzelił w ${coordinate} - pudło.`;
    }


    // Odświeżamy planszę gracza

    createBoard(
        leftBoardContainer,
        playerBoard,
        true
    );
}


// ==========================================
// PRZYCISK "STRZAŁ"
// ==========================================

shootButton.addEventListener("click", function () {

    shoot(shotInput.value);

    shotInput.value = "";
    shotInput.focus();
});


// ==========================================
// KLAWIATURA
// ==========================================

// Możemy wpisać np.:
//
// A1
// B7
// J10
//
// i nacisnąć Enter.

shotInput.addEventListener("keydown", function (event) {

    if (event.key === "Enter") {

        shoot(shotInput.value);

        shotInput.value = "";
    }
});