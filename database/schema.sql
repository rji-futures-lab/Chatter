--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.12
-- Dumped by pg_dump version 9.6.12

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: domains; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.domains (
    domain_set character varying NOT NULL,
    domain character varying NOT NULL,
    subset character varying NOT NULL
);


ALTER TABLE public.domains OWNER TO postgres;

--
-- Name: tweeted_hashtags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tweeted_hashtags (
    tweet_id bigint NOT NULL,
    hashtag character varying(255) NOT NULL
);


ALTER TABLE public.tweeted_hashtags OWNER TO postgres;

--
-- Name: tweeted_urls; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tweeted_urls (
    url text NOT NULL,
    tweet_id bigint NOT NULL,
    url_hash character varying(255) NOT NULL,
    real_url text,
    real_url_hash character varying(255),
    domain character varying(255) NOT NULL
);


ALTER TABLE public.tweeted_urls OWNER TO postgres;

--
-- Name: tweets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tweets (
    user_id bigint NOT NULL,
    tweet_id bigint NOT NULL,
    text character varying(300) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    retweeted_tweet_id bigint
);


ALTER TABLE public.tweets OWNER TO postgres;

--
-- Name: url_info; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.url_info (
    real_url_hash character varying(255) NOT NULL,
    title character varying,
    description text,
    image_url character varying
);


ALTER TABLE public.url_info OWNER TO postgres;

--
-- Name: url_topics; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.url_topics (
    real_url_hash character varying(255) NOT NULL,
    topic character varying(150) NOT NULL,
    score real
);


ALTER TABLE public.url_topics OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id bigint NOT NULL,
    list_id character varying,
    screen_name character varying(255) DEFAULT NULL::character varying,
    friends_count integer,
    followers_count integer,
    last_updated timestamp with time zone,
    suspended boolean DEFAULT false NOT NULL,
    source character varying(255) DEFAULT 'geo'::character varying NOT NULL,
    name character varying(255) DEFAULT NULL::character varying,
    profile_image_url text,
    home_domain character varying(255) DEFAULT NULL::character varying,
    home_domain_percent integer,
    location character varying(255) DEFAULT NULL::character varying,
    date_added timestamp with time zone
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (domain_set, domain, subset);


--
-- Name: tweeted_hashtags tweeted_hashtags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tweeted_hashtags
    ADD CONSTRAINT tweeted_hashtags_pkey PRIMARY KEY (tweet_id, hashtag);


--
-- Name: tweeted_urls tweeted_urls_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tweeted_urls
    ADD CONSTRAINT tweeted_urls_pkey PRIMARY KEY (tweet_id, url_hash);


--
-- Name: tweets tweets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tweets
    ADD CONSTRAINT tweets_pkey PRIMARY KEY (tweet_id);


--
-- Name: url_info url_info_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.url_info
    ADD CONSTRAINT url_info_pkey PRIMARY KEY (real_url_hash);


--
-- Name: url_topics url_topics_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.url_topics
    ADD CONSTRAINT url_topics_pkey PRIMARY KEY (real_url_hash, topic);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: created_at_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX created_at_idx ON public.tweets USING btree (created_at);


--
-- Name: real_url_hash_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX real_url_hash_idx ON public.tweeted_urls USING btree (real_url_hash);


--
-- PostgreSQL database dump complete
--

