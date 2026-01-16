"""
SEO Blueprint - Sitemap.xml & Robots.txt 동적 생성

이 블루프린트는 검색 엔진 최적화(SEO)를 위한 필수 파일들을 동적으로 생성합니다.
- Sitemap.xml: 검색 엔진이 크롤링할 페이지 목록
- Robots.txt: 크롤러 접근 규칙 정의

작성일: 2025-10-22
작성자: ECO-WEB Development Team
"""

from flask import Blueprint, Response, url_for, current_app
from datetime import datetime
import os

seo_bp = Blueprint('seo', __name__)


@seo_bp.route('/sitemap.xml')
def sitemap():
    """
    동적 Sitemap.xml 생성

    Google Search Console 및 기타 검색 엔진에 페이지 목록을 제공합니다.
    Static pages (index, follow)만 포함하며, dynamic pages는 제외합니다.

    Returns:
        Response: XML 형식의 sitemap
    """
    # 현재 시간 (ISO 8601 형식)
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Base URL 결정 (Production vs Development)
    flask_env = os.getenv('FLASK_ENV', 'production')
    if flask_env == 'production':
        base_url = 'https://example.com'
    else:
        base_url = 'http://localhost:5000'

    # Static pages 정의 (SEO 가치가 있는 페이지만)
    # Priority: 0.0 ~ 1.0 (1.0이 가장 중요)
    # Changefreq: always, hourly, daily, weekly, monthly, yearly, never
    static_pages = [
        {
            'loc': url_for('main.home', _external=True),
            'lastmod': current_date,
            'changefreq': 'daily',
            'priority': '1.0',
            'description': '홈페이지 - 탄소배출량 분석 시작'
        },
        {
            'loc': url_for('main.about', _external=True),
            'lastmod': current_date,
            'changefreq': 'weekly',
            'priority': '0.8',
            'description': 'eCarbon 소개 및 서비스 설명'
        },
        {
            'loc': url_for('main.guidelines_page', _external=True),
            'lastmod': current_date,
            'changefreq': 'monthly',
            'priority': '0.9',
            'description': 'W3C 웹 지속가능성 가이드라인'
        },
        {
            'loc': url_for('main.membership_plans', _external=True),
            'lastmod': current_date,
            'changefreq': 'monthly',
            'priority': '0.7',
            'description': '회원권 플랜 안내'
        },
        {
            'loc': url_for('main.badge', _external=True),
            'lastmod': current_date,
            'changefreq': 'monthly',
            'priority': '0.6',
            'description': 'eCarbon 뱃지 생성'
        }
    ]

    # XML 생성
    sitemap_xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    sitemap_xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for page in static_pages:
        sitemap_xml.append('  <url>')
        sitemap_xml.append(f'    <loc>{page["loc"]}</loc>')
        sitemap_xml.append(f'    <lastmod>{page["lastmod"]}</lastmod>')
        sitemap_xml.append(f'    <changefreq>{page["changefreq"]}</changefreq>')
        sitemap_xml.append(f'    <priority>{page["priority"]}</priority>')
        sitemap_xml.append('  </url>')

    sitemap_xml.append('</urlset>')

    # 로깅
    current_app.logger.info(f'Sitemap.xml generated with {len(static_pages)} URLs')

    return Response('\n'.join(sitemap_xml), mimetype='application/xml')


@seo_bp.route('/robots.txt')
def robots():
    """
    동적 Robots.txt 생성

    검색 엔진 크롤러에 대한 접근 규칙을 정의합니다.
    - Static pages: Allow (SEO 최적화 대상)
    - Dynamic pages: Disallow (noindex 전략과 일관성)
    - Admin/API: Disallow (보안)

    Returns:
        Response: Text 형식의 robots.txt
    """
    # Base URL 결정
    flask_env = os.getenv('FLASK_ENV', 'production')
    if flask_env == 'production':
        sitemap_url = 'https://example.com/sitemap.xml'
    else:
        sitemap_url = 'http://localhost:5000/sitemap.xml'

    # Robots.txt 내용
    robots_lines = [
        "# eCarbon Robots.txt",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "# 일반 크롤러 규칙",
        "User-agent: *",
        "",
        "# Static pages - Allow (SEO 최적화)",
        "Allow: /",
        "Allow: /about",
        "Allow: /guidelines",
        "Allow: /membership/plans",
        "Allow: /badge",
        "",
        "# Dynamic pages - Disallow (noindex 전략)",
        "Disallow: /carbon_calculate_emission/",
        "Disallow: /detailed-analysis",
        "Disallow: /code_analysis/",
        "Disallow: /img_optimization/",
        "",
        "# 시스템 페이지 - Disallow",
        "Disallow: /loading/",
        "Disallow: /error",
        "Disallow: /check_status/",
        "Disallow: /cancel_task/",
        "",
        "# 개발/관리자 - Disallow",
        "Disallow: /dev/",
        "Disallow: /admin/",
        "",
        "# API 엔드포인트 - Disallow",
        "Disallow: /api/",
        "Disallow: /auth/",
        "",
        "# PDF 관련 - Disallow",
        "Disallow: /generate-pdf-report",
        "Disallow: /download-pdf/",
        "Disallow: /pdf-status/",
        "",
        "# 다운로드 엔드포인트 - Disallow",
        "Disallow: /download-webp",
        "Disallow: /download-single-webp/",
        "Disallow: /download_code",
        "",
        "# Survey - Disallow",
        "Disallow: /check_survey_status",
        "Disallow: /submit_survey",
        "Disallow: /skip_survey",
        "",
        "# Monitoring - Disallow",
        "Disallow: /status",
        "Disallow: /processes",
        "Disallow: /lighthouse-stats",
        "Disallow: /health",
        "",
        "# Sitemap 위치",
        f"Sitemap: {sitemap_url}",
        "",
        "# Crawl-delay (서버 부하 방지)",
        "Crawl-delay: 1",
    ]

    # 로깅
    current_app.logger.info(f'Robots.txt generated for environment: {flask_env}')

    return Response('\n'.join(robots_lines), mimetype='text/plain')
