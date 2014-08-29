DROP TABLE IF EXISTS coin_data CASCADE;
CREATE TABLE coin_data (
    ticker varchar(10),
    name varchar(100),
    price numeric(24,8) CONSTRAINT nonnegative_price CHECK (price >= 0),
    price_btc numeric(24,8) CONSTRAINT nonnegative_price_btc CHECK (price_btc >= 0),
    volume_btc numeric CONSTRAINT nonnegative_volume CHECK (volume_btc >= 0),
    data_source varchar(1000),
    last_update timestamp DEFAULT statement_timestamp()
);
